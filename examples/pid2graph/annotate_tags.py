"""PID2Graph 도면의 기호 상자마다 OCR로 태그 후보를 제안해 사람이 확인할 주석 양식을 만든다.

graphml에는 문자 속성이 없으므로 질의응답 정답을 만들려면 기호마다 태그(장비·계기·밸브 번호)를 붙여야 한다.
도면 전체를 한 번 OCR한 뒤, 문자 상자를 기호 상자 안쪽(계기 원 안의 기능 문자와 번호)과
상자를 1.5배로 넓힌 주변(장비·밸브 옆 태그)으로 나눠 배정하고 제안 태그를 적는다.
기호 상자 밖의 긴 문자열(라인 사양 SIZE-…-SPEC 등)은 lines.csv에 따로 모은다.

사용: python annotate_tags.py <도면 폴더> <출력 폴더> [--only 5,7]
계기 기호는 원 하나만 따로 확대해 다시 읽은 값(계기 원 OCR)을 우선 제안한다.
제안 태그는 확인용 초안이며, 5번 도면 시험에서 번호까지 정확히 맞는 경우는 드물었다. 확정 태그는 조각 이미지를 보고 사람이 적는다.
결과: <출력>/<도면>.csv(도면, 노드 id, 종류, 상자, 안쪽 문자, 주변 문자, 계기 원 OCR, 제안 태그, 확정 태그=빈칸, 조각 이미지),
      <출력>/lines.csv(도면, 문자, 신뢰도, 상자), <출력>/crops/<도면>/<노드 id>.png
CSV는 엑셀에서 바로 열리도록 UTF-8(BOM)으로 쓴다. 데이터와 주석 결과는 저장소에 넣지 않는다.
"""
import os, sys, csv, glob, re, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gt_from_graphml as gg

SYMBOL_CLASSES = ('instrumentation', 'valve', 'general', 'tank', 'pump', 'inlet/outlet')
NEAR_SCALE = 1.5
LINE_SPEC = re.compile(r'(SIZE|SPEC)|^[A-Z0-9]+(-[A-Z0-9]+){3,}$', re.I)

def ocr(reader, png):
    import cv2
    gray = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
    out = []
    for q, s, c in res:
        xs = [p[0] for p in q]; ys = [p[1] for p in q]
        out.append(dict(text=s.strip(), conf=float(c), box=[min(xs), min(ys), max(xs), max(ys)]))
    return gray, out

def expand(b, k):
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    hw, hh = (b[2] - b[0]) * k / 2, (b[3] - b[1]) * k / 2
    return [cx - hw, cy - hh, cx + hw, cy + hh]

def overlap_ratio(t, b):
    """문자 상자 중 기호 상자와 겹치는 면적 비율"""
    w = min(t[2], b[2]) - max(t[0], b[0]); h = min(t[3], b[3]) - max(t[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / max(1e-6, (t[2] - t[0]) * (t[3] - t[1]))

def join_lines(items):
    """위에서 아래, 왼쪽에서 오른쪽 순서로 이어 붙임(계기 원의 'TE' / '1001A' → 'TE 1001A')"""
    items = sorted(items, key=lambda t: ((t['box'][1] + t['box'][3]) / 2, t['box'][0]))
    return ' '.join(t['text'] for t in items if t['text'])

def bubble_ocr(reader, gray, b):
    """계기 원 하나를 따로 읽음. 원 테두리를 흰색으로 지우고 4배 확대. 5번 도면 시험에서 기능 문자(TE, PT, LE)는
    12/12 맞았으나 번호는 원 가장자리에 걸린 첫 자리와 끝 문자(A/B)를 자주 틀림(정확 일치 0~1/12)"""
    import cv2, numpy as np
    c = gray[int(b[1]):int(b[3]), int(b[0]):int(b[2])].copy()
    if c.size == 0:
        return ''
    h, w = c.shape
    m = np.zeros_like(c); cv2.ellipse(m, (w // 2, h // 2), (int(w * 0.40), int(h * 0.40)), 0, 0, 360, 255, -1)
    c[m == 0] = 255
    c = cv2.resize(c, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    c = cv2.copyMakeBorder(c, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return ' '.join(reader.readtext(c, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-', detail=0))

def center_dist(t, b):
    return (((t[0] + t[2]) - (b[0] + b[2])) ** 2 + ((t[1] + t[3]) - (b[1] + b[3])) ** 2) ** 0.5 / 2

def annotate(png, gml, out_dir, reader, line_rows):
    import cv2
    name = os.path.splitext(os.path.basename(png))[0]
    nodes, _ = gg.load(gml)
    syms = []
    for nid, d in nodes.items():
        lab, bb = gg.label_of(d), gg.bbox_of(d)
        if bb and lab.lower() in SYMBOL_CLASSES:
            syms.append(dict(id=nid, cls=lab, bbox=bb))
    gray, texts = ocr(reader, png)
    H, W = gray.shape
    # 안쪽: 문자 상자의 절반 이상이 기호 상자 안. 한 문자는 한 기호에만 배정
    used = set()
    inside = {s['id']: [] for s in syms}
    for i, t in enumerate(texts):
        best = max(syms, key=lambda s: overlap_ratio(t['box'], s['bbox']), default=None)
        if best and overlap_ratio(t['box'], best['bbox']) >= 0.5:
            inside[best['id']].append(t); used.add(i)
    near = {s['id']: [] for s in syms}
    for i, t in enumerate(texts):
        if i in used:
            continue
        cands = [s for s in syms if overlap_ratio(t['box'], expand(s['bbox'], NEAR_SCALE)) > 0]
        if cands:
            near[min(cands, key=lambda s: center_dist(t['box'], s['bbox']))['id']].append(t); used.add(i)
    for i, t in enumerate(texts):
        if i not in used and LINE_SPEC.search(t['text'].replace(' ', '')):
            line_rows.append([name, t['text'], round(t['conf'], 2)] + [round(v) for v in t['box']])
    crop_dir = os.path.join(out_dir, 'crops', name); os.makedirs(crop_dir, exist_ok=True)
    rows = []
    for s in sorted(syms, key=lambda s: (s['bbox'][1], s['bbox'][0])):
        b = s['bbox']; e = expand(b, NEAR_SCALE)
        x0, y0 = max(0, int(e[0])), max(0, int(e[1])); x1, y1 = min(W, int(e[2]) + 1), min(H, int(e[3]) + 1)
        crop = os.path.join(crop_dir, f"{s['id']}.png")
        if x1 > x0 and y1 > y0:
            cv2.imwrite(crop, gray[y0:y1, x0:x1])
        tin, tnear = join_lines(inside[s['id']]), join_lines(near[s['id']])
        tbub = bubble_ocr(reader, gray, b) if s['cls'].lower() == 'instrumentation' else ''
        rows.append([name, s['id'], s['cls']] + [round(v, 1) for v in b] +
                    [tin, tnear, tbub, tbub or tin or tnear, '', os.path.relpath(crop, out_dir)])
    with open(os.path.join(out_dir, f'{name}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['도면', '노드', '종류', 'xmin', 'ymin', 'xmax', 'ymax', '안쪽 문자', '주변 문자', '계기 원 OCR', '제안 태그', '확정 태그', '조각 이미지'])
        w.writerows(rows)
    n_sug = sum(1 for r in rows if r[10])
    print(f'{name}: 기호 {len(rows)}, 제안 있음 {n_sug}, OCR 문자 {len(texts)}')
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('out'); ap.add_argument('--only', default='')
    a = ap.parse_args()
    only = set(a.only.split(',')) if a.only else None
    plans = []
    for png in sorted(glob.glob(os.path.join(a.root, '*.png'))):
        stem = os.path.splitext(png)[0]
        if os.path.exists(stem + '.graphml') and (not only or os.path.basename(stem) in only):
            plans.append((png, stem + '.graphml'))
    os.makedirs(a.out, exist_ok=True)
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    line_rows = []
    for png, gml in plans:
        annotate(png, gml, a.out, reader, line_rows)
    lines_csv = os.path.join(a.out, 'lines.csv')
    with open(lines_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['도면', '문자', '신뢰도', 'xmin', 'ymin', 'xmax', 'ymax'])
        w.writerows(line_rows)

if __name__ == '__main__':
    main()
