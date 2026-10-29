"""실제 문서 쪽(정비 지침서의 표·삽화 쪽, 치수·공차 도면)에서 문자·선·그림 영역과 그 관계를 뽑는다.

table 모드: 표의 격자(긴 수평·수직선)로 칸을 만들고 OCR 문자를 칸에 넣는다. 문자·선 밖의 잉크 덩어리는 그림 영역으로
보고 그림이 든 칸의 행과 묶는다(삽화-부품 번호-설명 행).
drawing 모드: 문자·주기 상자(callout)와 그 상자에서 출발하는 지시선(어느 방향이든 직선)을 찾아 상자-지시선-끝점
관계를 만든다. 가장 큰 잉크 덩어리를 부품 영역으로 본다.
정답 자료가 없으므로 수치는 추출 개수와 시간이고 정확도는 표본을 눈으로 대조해 따로 기록한다.
"""
import sys, json, time, math, collections
import numpy as np, cv2

def mm_of(dpi):
    return 25.4 / dpi

def ocr(gray, reader, k, min_conf=0.2):
    res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
    out = []
    for quad, s, conf in res:
        s = s.strip()
        if not s or conf < min_conf:
            continue
        xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
        out.append(dict(text=s, conf=round(float(conf), 2), box=[int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]))
    return out

def axis_mask(ink, k, min_mm, orient):
    px = max(3, int(round(min_mm / k)))
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (px, 1) if orient == 'h' else (1, px))
    return cv2.morphologyEx(ink, cv2.MORPH_OPEN, ker)

def erase(ink, texts, pad=1):
    out = ink.copy()
    for t in texts:
        x0, y0, x1, y1 = t['box']
        cv2.rectangle(out, (x0 - pad, y0 - pad), (x1 + pad, y1 + pad), 0, -1)
    return out

def components(mask, k, min_area_mm2=0.0, min_dim_mm=0.0):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a * k * k >= min_area_mm2 and max(w, h) * k >= min_dim_mm:
            out.append(dict(box=[int(x), int(y), int(x + w), int(y + h)], area_mm2=round(float(a * k * k), 1), label=i))
    return out, lab

def inside(pt, b, pad=0):
    return b[0] - pad <= pt[0] <= b[2] + pad and b[1] - pad <= pt[1] <= b[3] + pad

def center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

# ---------------- 표 쪽 ----------------
def table_mode(gray, ink, texts, k):
    hm = axis_mask(ink, k, 15.0, 'h'); vm = axis_mask(ink, k, 8.0, 'v')
    solid = cv2.dilate(cv2.bitwise_and(hm, vm), np.ones((5, 5), np.uint8))   # 두 방향 모두 긴 영역 = 채워진 면(그래프 막대 등), 선이 아님
    hm[solid > 0] = 0; vm[solid > 0] = 0
    grid = cv2.bitwise_or(hm, vm)
    regions, lab = components(cv2.dilate(grid, np.ones((5, 5), np.uint8)), k, min_area_mm2=40)
    regions = [r for r in regions if (r['box'][2] - r['box'][0]) * (r['box'][3] - r['box'][1]) * k * k >= 400]   # 외곽 상자 면적 기준(테두리만 있는 틀 포함)
    tables, frames = [], []
    for r in regions:
        x0, y0, x1, y1 = r['box']
        sub_h = hm[y0:y1, x0:x1]; sub_v = vm[y0:y1, x0:x1]
        rows_prof = (sub_h > 0).sum(axis=1) > 0.5 * (x1 - x0)
        cols_prof = (sub_v > 0).sum(axis=0) > 0.5 * (y1 - y0)
        def edges(prof, off):
            es, on = [], False
            for i, v in enumerate(prof):
                if v and not on:
                    es.append(i + off); on = True
                elif not v:
                    on = False
            return es
        ys = edges(rows_prof, y0); xs = edges(cols_prof, x0)
        if len(ys) < 3:
            frames.append(r['box']); continue                 # 가로 괘선이 둘 미만이면 표가 아니라 틀(그림·차트 테두리)
        if not xs or xs[0] > x0 + 3: xs = [x0] + xs
        if xs[-1] < x1 - 3: xs = xs + [x1]
        xs = [x for i, x in enumerate(xs) if i == 0 or (x - xs[i - 1]) * k >= 2.0]     # 2 mm 미만 열(테두리 이중선) 제거
        # 괘선 사이가 문자 여러 줄이면 문자 줄 기준으로 행을 더 나눔(괘선 없는 자료 행)
        inner = [t for t in texts if inside(center(t['box']), r['box'])]
        def line_groups(ts):
            ys_ = sorted(set(round(center(t['box'])[1]) for t in ts)); hs_ = [t['box'][3] - t['box'][1] for t in ts]
            gs = []
            for cy in ys_:
                if gs and cy - gs[-1][-1] < 0.7 * np.median(hs_):
                    gs[-1].append(cy)
                else:
                    gs.append([cy])
            return gs
        ys2 = [ys[0]]
        for ri in range(len(ys) - 1):
            band = [t for t in inner if ys[ri] <= center(t['box'])[1] < ys[ri + 1]]
            hs = [t['box'][3] - t['box'][1] for t in band]
            # 열마다 문자 줄 수를 세어, 두 열 이상이 같은 수의 줄(2줄 이상)을 가지면 자료 행이 괘선 없이 쌓인 것으로 보고 나눔
            per_col = []
            for ci in range(len(xs) - 1):
                ct = [t for t in band if xs[ci] <= center(t['box'])[0] < xs[ci + 1]]
                per_col.append(line_groups(ct) if ct else [])
            counts = collections.Counter(len(g) for g in per_col if len(g) >= 2)
            if counts and (ys[ri + 1] - ys[ri]) > 2.2 * np.median(hs):
                n_lines, n_cols = counts.most_common(1)[0]
                if n_cols >= 2 and n_lines >= 4:          # 줄 바꿈된 머리글(2~3줄)은 나누지 않음
                    ref = max((g for g in per_col if len(g) == n_lines), key=lambda g: sum(len(x) for x in g))
                    ys2 += [int((ref[i][-1] + ref[i + 1][0]) / 2) for i in range(len(ref) - 1)]
            ys2.append(ys[ri + 1])
        ys = ys2
        cells = []
        for ri in range(len(ys) - 1):
            row = []
            for ci in range(len(xs) - 1):
                cb = [xs[ci], ys[ri], xs[ci + 1], ys[ri + 1]]
                ts = [t['text'] for t in texts if inside(center(t['box']), cb)]
                row.append(dict(box=cb, text=' '.join(ts), figures=[]))
            cells.append(row)
        # 높이 1 mm 미만이고 문자가 없는 행(스캔 이중선)은 제거
        cells = [row for row in cells if (row[0]['box'][3] - row[0]['box'][1]) * k >= 1.0 or any(c['text'] for c in row)]
        if len(cells) < 2 or len(xs) - 1 < 2:
            frames.append(r['box']); continue              # 열이 하나뿐이면 표가 아니라 틀
        tables.append(dict(box=[int(v) for v in r['box']], rows=cells, n_rows=len(cells), n_cols=len(xs) - 1))
    # 그림 영역: 문자·격자 밖의 잉크 덩어리. 가늘고 긴 조각(선)은 제외
    resid = erase(ink, texts, 2)
    resid[cv2.dilate(grid, np.ones((5, 5), np.uint8)) > 0] = 0
    resid = cv2.morphologyEx(resid, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    figs, _ = components(resid, k, min_area_mm2=6.0, min_dim_mm=4.0)
    figs = [f for f in figs if min(f['box'][2] - f['box'][0], f['box'][3] - f['box'][1]) * k >= 1.0]
    figs = [f for f in figs if not ((f['box'][3] - f['box'][1]) * k < 5.0 and (f['box'][2] - f['box'][0]) > 8 * (f['box'][3] - f['box'][1]))]   # 높이 5 mm 미만의 긴 띠(문자 줄)는 제외
    # 틀(차트 테두리 등) 안의 조각과 문자는 틀 하나의 그림으로 묶음
    merged = []
    for fb in frames:
        if any(inside(center(fb), t['box']) for t in tables):
            continue
        inner_f = [f for f in figs if inside(center(f['box']), fb)]
        inner_t = [t for t in texts if inside(center(t['box']), fb)]
        figs = [f for f in figs if f not in inner_f]
        merged.append(dict(box=[int(v) for v in fb], area_mm2=round((fb[2] - fb[0]) * (fb[3] - fb[1]) * k * k, 1), frame=True,
                           texts=[t['text'] for t in sorted(inner_t, key=lambda t: (t['box'][1], t['box'][0]))]))
    # 표 밖의 가까운 조각(6 mm 안)끼리 병합
    outside = [f for f in figs if not any(inside(center(f['box']), t['box']) for t in tables)]
    figs = [f for f in figs if f not in outside]
    pad = int(6.0 / k)
    changed = True
    while changed:
        changed = False
        for i in range(len(outside)):
            for j in range(i + 1, len(outside)):
                a, b = outside[i]['box'], outside[j]['box']
                if a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]:
                    nb = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    outside[i] = dict(box=nb, area_mm2=round(outside[i]['area_mm2'] + outside[j]['area_mm2'], 1)); del outside[j]; changed = True; break
            if changed:
                break
    figs = figs + outside + merged
    figs.sort(key=lambda f: (f['box'][1], f['box'][0]))
    linked = 0
    for f in figs:
        c = center(f['box']); f['table'] = None
        for ti, tb in enumerate(tables):
            for ri, row in enumerate(tb['rows']):
                for ci, cell in enumerate(row):
                    if inside(c, cell['box']):
                        cell['figures'].append(f['box']); f['table'] = [ti, ri, ci]; linked += 1
    # 행 단위 묶음: 그림이 든 행의 문자 칸
    rows_with_fig = []
    for ti, tb in enumerate(tables):
        for ri, row in enumerate(tb['rows']):
            if any(c['figures'] for c in row):
                rows_with_fig.append(dict(table=ti, row=ri, cells=[c['text'] for c in row]))
    return dict(tables=[dict(box=t['box'], n_rows=t['n_rows'], n_cols=t['n_cols'],
                             rows=[[c['text'] for c in r] for r in t['rows']], cell_boxes=[[c['box'] for c in r] for r in t['rows']]) for t in tables],
                figures=figs, figure_rows=rows_with_fig, frames=frames,
                summary=dict(tables=len(tables), cells=sum(t['n_rows'] * t['n_cols'] for t in tables),
                             figures=len(figs), figures_in_cells=linked, rows_with_figure=len(rows_with_fig)))

# ---------------- 도면 쪽 ----------------
def drawing_mode(gray, ink, texts, k):
    H, W = ink.shape
    noink = erase(ink, texts, 1)
    # 주기 상자: 문자 상자를 2 mm 안에서 묶어 한 주기(callout)로 본다. 가로로 이어진 줄과 세로로 쌓인 줄 모두 묶음
    n = len(texts); parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    pad = int(2.0 / k)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = texts[i]['box'], texts[j]['box']
            if a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]:
                parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    callouts = []
    for g in groups.values():
        bs = [texts[i]['box'] for i in g]
        callouts.append(dict(box=[min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)],
                             texts=[texts[i]['text'] for i in sorted(g, key=lambda i: (texts[i]['box'][1] // max(1, pad), texts[i]['box'][0]))]))
    # 부품 영역: 가장 큰 잉크 덩어리(음영 포함)
    closed = cv2.morphologyEx(noink, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    comps, lab = components(closed, k, min_area_mm2=0)
    part = max(comps, key=lambda c: c['area_mm2']) if comps else None
    part_mask = (lab == part['label']).astype(np.uint8) * 255 if part else np.zeros_like(ink)
    # 지시선: 어느 방향이든 직선 조각(4 mm 이상). 한 끝이 주기 상자 3 mm 안, 다른 끝은 상자에서 5 mm 이상 떨어짐
    thin = cv2.ximgproc.thinning(noink) if hasattr(cv2, 'ximgproc') else noink
    segs = cv2.HoughLinesP(thin, 1, np.pi / 360, threshold=int(3.0 / k), minLineLength=int(4.0 / k), maxLineGap=int(1.0 / k))
    segs = [tuple(int(v) for v in s) for s in np.asarray(segs).reshape(-1, 4)] if segs is not None else []
    leaders = []
    for (x0, y0, x1, y1) in segs:
        for ci, c in enumerate(callouts):
            b = c['box']
            for near, far in (((x0, y0), (x1, y1)), ((x1, y1), (x0, y0))):
                if inside(near, b, int(3.0 / k)) and not inside(far, b, int(5.0 / k)):
                    L = math.hypot(x1 - x0, y1 - y0) * k
                    on_part = bool(cv2.dilate(part_mask, np.ones((7, 7), np.uint8))[min(H - 1, far[1]), min(W - 1, far[0])])
                    leaders.append(dict(callout=ci, start=list(near), end=list(far), length_mm=round(L, 1), end_on_part=on_part))
                    break
    # 주기당 지시선 하나: 가장 긴 것
    best = {}
    for l in leaders:
        if l['callout'] not in best or l['length_mm'] > best[l['callout']]['length_mm']:
            best[l['callout']] = l
    leaders = list(best.values())
    return dict(callouts=callouts, leaders=leaders, part_box=part['box'] if part else None,
                summary=dict(texts=len(texts), callouts=len(callouts), callouts_with_leader=len(leaders),
                             leader_end_on_part=sum(1 for l in leaders if l['end_on_part']), segments=len(segs)))

def overlay(gray, texts, result, mode, out_png):
    im = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for t in texts:
        x0, y0, x1, y1 = t['box']; cv2.rectangle(im, (x0, y0), (x1, y1), (255, 160, 0), 1)
    if mode == 'table':
        for tb in result['tables']:
            x0, y0, x1, y1 = tb['box']; cv2.rectangle(im, (x0, y0), (x1, y1), (0, 0, 255), 2)
        for f in result['figures']:
            x0, y0, x1, y1 = f['box']; cv2.rectangle(im, (x0, y0), (x1, y1), (0, 160, 0) if f.get('table') else (160, 160, 160), 2)
    else:
        if result['part_box']:
            x0, y0, x1, y1 = result['part_box']; cv2.rectangle(im, (x0, y0), (x1, y1), (160, 160, 160), 1)
        for c in result['callouts']:
            x0, y0, x1, y1 = c['box']; cv2.rectangle(im, (x0, y0), (x1, y1), (200, 0, 200), 1)
        for l in result['leaders']:
            cv2.line(im, tuple(l['start']), tuple(l['end']), (0, 160, 0) if l['end_on_part'] else (0, 0, 255), 2)
            cv2.circle(im, tuple(l['end']), 5, (0, 0, 255), 2)
    cv2.imwrite(out_png, im)

def main(img, dpi, mode, out_prefix, reader=None):
    t0 = time.time()
    gray = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
    k = mm_of(dpi)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    import os
    cache = out_prefix + '_ocr.json'
    if os.path.exists(cache):
        texts = json.load(open(cache))
    else:
        if reader is None:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        texts = ocr(gray, reader, k)
        json.dump(texts, open(cache, 'w'))
    t_ocr = time.time() - t0; t1 = time.time()
    res = table_mode(gray, ink, texts, k) if mode == 'table' else drawing_mode(gray, ink, texts, k)
    res['texts'] = texts
    res['times'] = dict(ocr=round(t_ocr, 1), structure=round(time.time() - t1, 1), total=round(time.time() - t0, 1))
    res['image'] = dict(path=img, px=[int(gray.shape[1]), int(gray.shape[0])], dpi=dpi)
    res['summary']['mean_conf'] = round(float(np.mean([t['conf'] for t in texts])), 2) if texts else 0
    json.dump(res, open(out_prefix + '.json', 'w'), ensure_ascii=False, indent=1)
    overlay(gray, texts, res, mode, out_prefix + '-overlay.png')
    print(img, res['summary'], res['times'])
    return res

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4])
