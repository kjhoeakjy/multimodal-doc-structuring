"""래스터(스캔·PNG) 도면에서 관계 그래프를 만든다.

문자는 OCR로 읽어 지운 뒤, 축 평행 긴 선은 형태학 연산으로, 닫힌 윤곽은 구멍 탐지로,
나머지 잉크 덩어리는 기호로 본다. 이후 연결·문자 부착은 벡터 경로(extract_graph.assemble)와 같다.
"""
import sys, json, math, time, collections
import numpy as np, cv2
from shapely.geometry import LineString, box, Polygon
from shapely.ops import unary_union
import extract_graph as eg

def mm_of(dpi):
    return 25.4 / dpi

def ocr_texts(gray, dpi, reader, res=None):
    k = mm_of(dpi)
    if res is None:
        res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
    texts, boxes = [], []
    for quad, s, conf in res:
        s = s.strip()
        if not s or conf < 0.2:
            continue
        xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        boxes.append((int(x0), int(y0), int(x1), int(y1)))
        texts.append(dict(text=s, x=x0 * k, y=y1 * k, angle=0, size=(y1 - y0) * k, anchor='start',
                          width=(x1 - x0) * k, conf=round(float(conf), 2)))
    return texts, boxes

def axis_lines(ink, dpi, min_mm, orient):
    """orient 'h' 또는 'v'. 형태학 열림으로 긴 축 평행 선을 찾아 (선분, 굵기)로 돌려준다."""
    px = max(3, int(round(min_mm / mm_of(dpi))))
    ker = cv2.getStructuringElement(cv2.MORPH_RECT, (px, 1) if orient == 'h' else (1, px))
    mask = cv2.morphologyEx(ink, cv2.MORPH_OPEN, ker)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    k = mm_of(dpi)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if orient == 'h':
            thick = area / max(1, w)
            a, b = (x * k, (y + h / 2) * k), ((x + w) * k, (y + h / 2) * k)
            L = w * k
        else:
            thick = area / max(1, h)
            a, b = ((x + w / 2) * k, y * k), ((x + w / 2) * k, (y + h) * k)
            L = h * k
        out.append(dict(kind='line', geom=LineString([a, b]), ends=[a, b], length=L, axis=True,
                        width=round(thick * k, 2), dashed=False, id=len(out)))
    return out, mask

def dashed_lines(short, dpi, gap_mm=2.5, min_total=eg.LONG):
    """짧은 축 평행 조각을 같은 축에서 이어 붙여 점선으로 본다."""
    groups = collections.defaultdict(list)
    for p in short:
        (x0, y0), (x1, y1) = p['ends']
        if abs(y0 - y1) < 1e-6:
            groups[('h', round(y0 / 0.6))].append((min(x0, x1), max(x0, x1), p))
        else:
            groups[('v', round(x0 / 0.6))].append((min(y0, y1), max(y0, y1), p))
    dashed, used = [], set()
    for (o, c), ivs in groups.items():
        ivs.sort(key=lambda t: t[0])
        chain = [ivs[0]]
        def flush(chain):
            if len(chain) >= 3 and chain[-1][1] - chain[0][0] >= min_total:
                cc = np.mean([p['ends'][0][1] if o == 'h' else p['ends'][0][0] for _, _, p in chain])
                a, b = ((chain[0][0], cc), (chain[-1][1], cc)) if o == 'h' else ((cc, chain[0][0]), (cc, chain[-1][1]))
                dashed.append(dict(kind='line', geom=LineString([a, b]), ends=[a, b], length=math.dist(a, b), axis=True,
                                   width=round(float(np.median([p['width'] for _, _, p in chain])), 2), dashed=True))
                used.update(id(p) for _, _, p in chain)
        for iv in ivs[1:]:
            if iv[0] - chain[-1][1] <= gap_mm:
                chain.append(iv)
            else:
                flush(chain); chain = [iv]
        flush(chain)
    rest = [p for p in short if id(p) not in used]
    return dashed, rest

def closed_shapes(ink, dpi, line_mask, ext_lines=()):
    """잉크로 둘러싸인 구멍 중 장비 윤곽으로 볼 만한 것: 곡선 경계가 있거나 안쪽에 장식 잉크가 있음."""
    k = mm_of(dpi)
    contours, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    shapes, shape_mask = [], np.zeros_like(ink)
    if hier is None:
        return shapes, shape_mask
    H, W = ink.shape
    for i, c in enumerate(contours):
        if hier[0][i][3] < 0:          # 바깥 윤곽은 건너뜀. 구멍(안쪽 윤곽)만 본다
            continue
        area = cv2.contourArea(c) * k * k
        if area < 30 or area > 0.08 * W * H * k * k:
            continue
        x, y, w, h = cv2.boundingRect(c)
        if w < 3 or h < 3:
            continue
        # 경계가 긴 축 평행 선으로만 이루어졌는지
        bmask = np.zeros_like(ink); cv2.drawContours(bmask, [c], -1, 255, 2)
        bpix = bmask > 0
        covered = (line_mask[bpix] > 0).mean() if bpix.any() else 1.0
        inner = np.zeros_like(ink); cv2.drawContours(inner, [c], -1, 255, -1)
        inner = cv2.erode(inner, np.ones((5, 5), np.uint8))
        # 안쪽 잉크 중 3 mm 이상 뻗은 덩어리(기호의 내부 선)가 있으면 장비. 남은 글자 조각은 무시
        sub = cv2.bitwise_and(ink, inner)
        big = False
        if sub.any():
            nn, _, st, _ = cv2.connectedComponentsWithStats(sub, connectivity=8)
            big = any(max(st[j][2], st[j][3]) * k >= 3.0 for j in range(1, nn))
        # 경계의 절반 이상이 윤곽 밖으로 이어지는 긴 선(배관)으로 덮이면 배관에 둘러싸인 빈 영역이지 장비가 아님
        ext = np.zeros_like(ink)
        bx0, by0, bx1, by1 = (x - 2 / k), (y - 2 / k), (x + w + 2 / k), (y + h + 2 / k)
        for l in ext_lines:
            (lx0, ly0), (lx1, ly1) = l['ends']
            px = [(int(lx0 / k), int(ly0 / k)), (int(lx1 / k), int(ly1 / k))]
            if (px[0][0] < bx0 or px[0][0] > bx1 or px[0][1] < by0 or px[0][1] > by1 or
                    px[1][0] < bx0 or px[1][0] > bx1 or px[1][1] < by0 or px[1][1] > by1):
                if min(px[0][0], px[1][0]) <= x + w and max(px[0][0], px[1][0]) >= x and \
                        min(px[0][1], px[1][1]) <= y + h and max(px[0][1], px[1][1]) >= y:
                    cv2.line(ext, px[0], px[1], 255, 3)
        covered_ext = (ext[bpix] > 0).mean() if bpix.any() else 0.0
        if covered_ext > 0.5:
            continue
        if covered < 0.8 or big:
            poly = [(p[0][0] * k, p[0][1] * k) for p in c]
            if len(poly) >= 3:
                shapes.append(dict(role='shape', prims=[], geom=LineString(poly + [poly[0]]),
                                   bbox=[x * k, y * k, (x + w) * k, (y + h) * k]))
                cv2.drawContours(shape_mask, [c], -1, 255, 3)
    return shapes, shape_mask

def deskew(gray):
    """긴 선 성분마다 직선을 맞춰 각도를 재고 그 중앙값으로 되돌린다. 2도 이내만 보정."""
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    H, W = gray.shape
    angs = []
    for orient in ('h', 'v'):
        ker = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1) if orient == 'h' else (1, 20))
        mask = cv2.morphologyEx(ink, cv2.MORPH_OPEN, ker)
        n, lab, st, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if (orient == 'h' and w < 0.1 * W) or (orient == 'v' and h < 0.1 * H):
                continue
            ys, xs = np.nonzero(lab[y:y + h, x:x + w] == i)
            vx, vy, _, _ = cv2.fitLine(np.column_stack([xs, ys]).astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01)
            ang = math.degrees(math.atan2(float(vy[0]), float(vx[0])))
            ang = (ang + 90) % 180 - 90
            if orient == 'v':
                ang = ang - 90 if ang > 0 else ang + 90
            if abs(ang) < 2:
                angs.append(ang)
    if len(angs) < 3:
        return gray, 0.0
    ang = float(np.median(angs))
    if abs(ang) < 0.05:
        return gray, ang
    M = cv2.getRotationMatrix2D((W / 2, H / 2), ang, 1.0)
    return cv2.warpAffine(gray, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=255), ang

def inner_frame(lines, W, H, band=20.0):
    """가장자리 띠 안의 긴 수평·수직선 중 가장 안쪽 네 개로 도면 틀을 정한다. 없으면 쪽 전체."""
    top, bottom, left, right = 0.0, H, 0.0, W
    for l in lines:
        (x0, y0), (x1, y1) = l['ends']
        if abs(y0 - y1) < 1e-6 and l['length'] >= 0.6 * W:
            if y0 < band: top = max(top, y0)
            if y0 > H - band: bottom = min(bottom, y0)
        if abs(x0 - x1) < 1e-6 and l['length'] >= 0.6 * H:
            if x0 < band: left = max(left, x0)
            if x0 > W - band: right = min(right, x0)
    return box(left, top, right, bottom)

def main(png_path, dpi, out_prefix, reader=None, ocr_json=None):
    t0 = time.time(); times = {}
    gray = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    gray = cv2.medianBlur(gray, 3)                       # 스캔 잡음 제거
    gray, skew = deskew(gray)                             # 스캔 기울기 보정. 축 평행 선 탐지의 전제
    cv2.imwrite(out_prefix + '_input.png', gray)
    Hpx, Wpx = gray.shape
    k = mm_of(dpi); W, H = Wpx * k, Hpx * k
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # 1. 문자
    if ocr_json:
        texts, boxes = ocr_texts(gray, dpi, None, res=json.load(open(ocr_json)))
    else:
        if reader is None:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
        json.dump([[[[float(v) for v in p] for p in q], s_, float(c)] for q, s_, c in res], open(out_prefix + '_ocr.json', 'w'))
        texts, boxes = ocr_texts(gray, dpi, None, res=res)
    times['ocr'] = round(time.time() - t0, 1); t1 = time.time()
    # 2. 긴 축 평행 선. 문자를 지우기 전에 찾아 두어 문자 상자를 지나는 선이 끊기지 않게 한다
    hl, hm = axis_lines(ink, dpi, eg.LONG, 'h')
    vl, vm = axis_lines(ink, dpi, eg.LONG, 'v')
    line_mask = cv2.bitwise_or(hm, vm)
    tmask = np.zeros_like(ink)
    for x0, y0, x1, y1 in boxes:
        cv2.rectangle(tmask, (x0 - 1, y0 - 1), (x1 + 1, y1 + 1), 255, -1)
    noink = ink.copy()
    noink[tmask > 0] = 0
    noink[(tmask > 0) & (line_mask > 0)] = 255
    # 3. 닫힌 윤곽(장비). 선을 지운 그림에서 곡선 윤곽을, 원본에서 직선 변을 가진 윤곽을 찾아 합친다
    nolines = noink.copy()
    nolines[cv2.dilate(line_mask, np.ones((3, 3), np.uint8)) > 0] = 0
    # 경계가 직선 조각(2 mm 이상)으로만 이루어지고 안이 빈 구멍은 표·틀의 칸이므로 장비로 보지 않는다
    _, sm_h = axis_lines(noink, dpi, 2.0, 'h'); _, sm_v = axis_lines(noink, dpi, 2.0, 'v')
    straight_mask = cv2.bitwise_or(sm_h, sm_v)
    shapes1, mask1 = closed_shapes(nolines, dpi, straight_mask, hl + vl)
    shapes2, mask2 = closed_shapes(noink, dpi, straight_mask, hl + vl)
    shapes = list(shapes1)
    for s2 in shapes2:
        b2 = box(*s2['bbox'])
        if not any(box(*s1['bbox']).intersection(b2).area > 0.5 * min(b2.area, box(*s1['bbox']).area) for s1 in shapes1):
            shapes.append(s2)
    shape_mask = np.zeros_like(ink)
    for s in shapes:
        pts = np.array([(int(x / k), int(y / k)) for x, y in s['geom'].coords], np.int32)
        cv2.polylines(shape_mask, [pts], True, 255, 3)
    # 윤곽에 걸친 선 조각은 선에서 뺀다
    def on_shape(l):
        (x0, y0), (x1, y1) = l['ends']
        px = [(int(x0 / k), int(y0 / k)), (int(x1 / k), int(y1 / k))]
        m = np.zeros_like(ink); cv2.line(m, px[0], px[1], 255, 3)
        both = (m > 0) & (shape_mask > 0)
        return both.sum() > 0.8 * (m > 0).sum()
    lines = [l for l in hl + vl if not on_shape(l)]
    # 4. 나머지 잉크: 선·윤곽을 지운 뒤 덩어리 = 기호. 짧은 축 평행 조각은 점선 후보
    resid = noink.copy()
    resid[cv2.dilate(line_mask, np.ones((3, 3), np.uint8)) > 0] = 0
    resid[shape_mask > 0] = 0
    sh, shm = axis_lines(resid, dpi, 1.0, 'h'); sv, svm = axis_lines(resid, dpi, 1.0, 'v')
    dashed, rest = dashed_lines([p for p in sh + sv if p['length'] < eg.LONG], dpi)
    for d in dashed:
        (x0, y0), (x1, y1) = d['ends']
        cv2.line(resid, (int(x0 / k), int(y0 / k)), (int(x1 / k), int(y1 / k)), 0, 5)
    lines += dashed
    resid = cv2.morphologyEx(resid, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(resid, connectivity=8)
    symbols = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area * k * k < 0.15:
            continue
        comp = (lab == i).astype(np.uint8) * 255
        cs, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        poly = [(p[0][0] * k, p[0][1] * k) for p in c]
        geom = LineString(poly + [poly[0]]) if len(poly) >= 3 else box(x * k, y * k, (x + w) * k, (y + h) * k).exterior
        symbols.append(dict(role='mark' if max(w, h) * k < 1.2 else 'symbol', prims=[], geom=geom,
                            bbox=[x * k, y * k, (x + w) * k, (y + h) * k]))
    # 5. 도면 틀: 가장자리 띠(20 mm) 안에서 쪽 길이의 6할 이상인 선 중 가장 안쪽 것을 틀로 보고 그 밖은 버린다
    fb = inner_frame(hl + vl, W, H)
    inner = fb.buffer(-eg.TOUCH)
    lines = [l for l in lines if l['geom'].within(inner)]
    shapes = [s_ for s_ in shapes if box(*s_['bbox']).within(inner.buffer(0.5))]
    symbols = [s_ for s_ in symbols if box(*s_['bbox']).centroid.within(inner)]
    texts = [t for t in texts if eg.text_bbox(t).centroid.within(inner)]
    # 틀·표 제거는 벡터 경로의 규칙을 선에 그대로 적용
    for i, l in enumerate(lines):
        l['id'] = i
    lines, texts, tables = eg.remove_frame_and_tables(W, H, lines, texts)
    tb = [box(*t['bbox']) for t in tables]
    nodes = [s for s in shapes + symbols if not any(box(*s['bbox']).within(b.buffer(0.5)) for b in tb)]
    times['lines_symbols'] = round(time.time() - t1, 1); t2 = time.time()
    eg.SIGNAL_RATIO = 0.35     # 래스터에서는 선 굵기 측정 오차가 커 신호선 판정 비율을 낮춘다
    out = eg.assemble(W, H, nodes, lines, texts, tables, out_prefix, n_prims=len(lines) + len(nodes))
    times['graph'] = round(time.time() - t2, 1); times['total'] = round(time.time() - t0, 1)
    out['times'] = times
    out['dpi'] = dpi
    out['skew_deg'] = round(skew, 2)
    json.dump(out, open(out_prefix + '.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print('times', times)
    return out

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3], ocr_json=(sys.argv[4] if len(sys.argv) > 4 else None))
