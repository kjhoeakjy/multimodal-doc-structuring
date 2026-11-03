"""PID2Graph 도면의 기호 상자마다 OCR로 태그 후보를 제안해 사람이 확인할 주석 양식을 만든다.

graphml에는 문자 속성이 없으므로 질의응답 정답을 만들려면 기호마다 태그(장비·계기·밸브 번호)를 붙여야 한다.
- 계기 원: 원 하나를 4배 확대해 PaddleOCR(별도 가상환경, paddle_crops.py)로 읽는다. 5번 도면 32개 모두 정확 일치,
  글자가 가장 작은 4번 도면은 12개 중 6개(끝 B를 8로 읽는 오류가 많음). 끝이 8이면 'B 후보' 열에 B로 바꾼 값을 적되 자동 치환은 하지 않는다.
- 밸브·장비: 상자를 3배로 넓힌 영역을 0°/90°/270° 회전해 EasyOCR로 읽고 태그 모양의 문자만 고른다(세로 태그가 많음).
  숫자 자리의 I→1, O→0을 정규화한다. 5번 도면 밸브 19개 중 11개 정확(정규화 전).
- 그 밖에 도면 전체 OCR의 안쪽·주변(1.5배) 문자, 기호 밖 긴 문자열(라인 사양 SIZE-…-SPEC 등, lines.csv)도 남긴다.

사용: python annotate_tags.py <도면 폴더> <출력 폴더> [--only 6,5,7] [--paddle-python C:/data/ocr-venv/Scripts/python.exe]
      --only 순서대로 처리한다. OCR 결과는 <출력>/cache/에 저장해 다시 실행할 때 재사용한다.
결과: <출력>/<도면>.csv, <출력>/lines.csv, <출력>/crops/<도면>/<노드 id>.png
CSV는 엑셀에서 바로 열리도록 UTF-8(BOM)으로 쓴다. 데이터와 주석 결과는 저장소에 넣지 않는다.
"""
import os, sys, csv, glob, re, json, argparse, subprocess, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gt_from_graphml as gg

SYMBOL_CLASSES = ('instrumentation', 'valve', 'general', 'tank', 'pump', 'inlet/outlet')
TAGGED_BY_REGION = ('valve', 'general', 'tank', 'pump')
NEAR_SCALE, REGION_SCALE = 1.5, 3.0
# 계기 원 높이 중앙값이 45 px 이상인 큰 글씨 도면(8, 5, 9, 6, 7번). 이 도면의 계기 원 OCR은 자동 신뢰 '높음'
LARGE_TEXT_MIN_PX = 45
DEFAULT_PADDLE = 'C:/data/ocr-venv/Scripts/python.exe'
LINE_SPEC = re.compile(r'(SIZE|SPEC)|^[A-Z0-9]+(-[A-Z0-9]+){3,}$', re.I)
VALVE_TAG = re.compile(r'V-?[A-Z0-9]-?[0-9A-Z]{3,5}')
EQUIP_TAG = re.compile(r'[A-Z]{2,}[-_][A-Z0-9]+(?:[-_][A-Z0-9]+)*')
ALLOW = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'

def ocr(reader, gray):
    res = reader.readtext(gray, paragraph=False, min_size=4, text_threshold=0.6, low_text=0.3, mag_ratio=1.5)
    out = []
    for q, s, c in res:
        xs = [float(p[0]) for p in q]; ys = [float(p[1]) for p in q]
        out.append(dict(text=s.strip(), conf=float(c), box=[min(xs), min(ys), max(xs), max(ys)]))
    return out

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
    """위에서 아래, 왼쪽에서 오른쪽 순서로 이어 붙임"""
    items = sorted(items, key=lambda t: ((t['box'][1] + t['box'][3]) / 2, t['box'][0]))
    return ' '.join(t['text'] for t in items if t['text'])

def center_dist(t, b):
    return (((t[0] + t[2]) - (b[0] + b[2])) ** 2 + ((t[1] + t[3]) - (b[1] + b[3])) ** 2) ** 0.5 / 2

def norm_digits(tag):
    """첫 하이픈 뒤 조각의 I·L→1, O→0. 두 글자 이상 조각의 끝 글자(접미 X·A·B)는 그대로 (V-1-I00X, V-I-100X → V-1-100X)"""
    fix = {'I': '1', 'L': '1', 'O': '0'}
    parts = re.split(r'([-_])', tag)
    for i in range(2, len(parts), 2):
        p = parts[i]
        body, tail = (p[:-1], p[-1]) if len(p) > 1 else (p, '')
        parts[i] = ''.join(fix.get(ch, ch) for ch in body) + tail
    return ''.join(parts)

def crop(gray, b, scale=1.0, up=1):
    import cv2
    H, W = gray.shape
    e = expand(b, scale)
    x0, y0, x1, y1 = max(0, int(e[0])), max(0, int(e[1])), min(W, int(e[2]) + 1), min(H, int(e[3]) + 1)
    c = gray[y0:y1, x0:x1]
    if c.size == 0:
        return None
    if up > 1:
        c = cv2.resize(c, None, fx=up, fy=up, interpolation=cv2.INTER_CUBIC)
    return c

def region_tag(reader, gray, b, cls):
    """3배 영역을 세 방향으로 읽어 태그 모양 문자 중 가장 자주 나온 것"""
    import cv2
    c = crop(gray, b, REGION_SCALE, 2)
    if c is None:
        return ''
    pat = VALVE_TAG if cls == 'valve' else EQUIP_TAG
    cands = []
    for img in (c, cv2.rotate(c, cv2.ROTATE_90_CLOCKWISE), cv2.rotate(c, cv2.ROTATE_90_COUNTERCLOCKWISE)):
        for s in reader.readtext(img, allowlist=ALLOW, detail=0):
            m = pat.search(s.replace(' ', ''))
            if m:
                cands.append(norm_digits(m.group().replace('_', '-')))
    if not cands:
        return ''
    cnt = collections.Counter(cands)
    return max(cnt, key=lambda k: (cnt[k], len(k)))

def bubble_ocr(paddle_python, gray, syms, cache_json, work_dir):
    """계기 원 조각을 4배 확대해 저장하고 PaddleOCR 가상환경에서 한 번에 읽음"""
    import cv2
    if os.path.exists(cache_json):
        return json.load(open(cache_json, encoding='utf-8'))
    os.makedirs(work_dir, exist_ok=True)
    for s in syms:
        c = crop(gray, s['bbox'], 1.0, 4)
        if c is not None:
            c = cv2.copyMakeBorder(c, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
            cv2.imwrite(os.path.join(work_dir, f"{s['id']}.png"), cv2.cvtColor(c, cv2.COLOR_GRAY2BGR))
    env = dict(os.environ, FLAGS_use_mkldnn='0', PYTHONUTF8='1')
    subprocess.run([paddle_python, os.path.join(HERE, 'paddle_crops.py'), work_dir, cache_json], check=True, env=env)
    return json.load(open(cache_json, encoding='utf-8'))

def b_candidate(tag):
    """계기 번호 끝 '8'은 원에 걸린 'B'를 잘못 읽은 경우가 많음(4번 도면). 바꾼 값을 후보로만 적음"""
    m = re.match(r'^(.*\d)8$', tag.strip())
    return m.group(1) + 'B' if m else ''

def annotate(png, gml, out_dir, reader, paddle_python, line_rows):
    import cv2, statistics
    name = os.path.splitext(os.path.basename(png))[0]
    nodes, _ = gg.load(gml)
    syms = []
    for nid, d in nodes.items():
        lab, bb = gg.label_of(d), gg.bbox_of(d)
        if bb and lab.lower() in SYMBOL_CLASSES:
            syms.append(dict(id=nid, cls=lab.lower(), bbox=bb))
    gray = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    H, W = gray.shape
    cache = os.path.join(out_dir, 'cache'); os.makedirs(cache, exist_ok=True)
    page_json = os.path.join(cache, f'{name}_page.json')
    if os.path.exists(page_json):
        texts = json.load(open(page_json, encoding='utf-8'))
    else:
        texts = ocr(reader, gray)
        json.dump(texts, open(page_json, 'w', encoding='utf-8'), ensure_ascii=False)
    inst = [s for s in syms if s['cls'] == 'instrumentation']
    bubble_h = statistics.median([s['bbox'][3] - s['bbox'][1] for s in inst]) if inst else 0
    large = bubble_h >= LARGE_TEXT_MIN_PX
    bub = bubble_ocr(paddle_python, gray, inst, os.path.join(cache, f'{name}_paddle.json'), os.path.join(cache, f'{name}_bubbles')) if inst else {}
    region_json = os.path.join(cache, f'{name}_region.json')
    region = json.load(open(region_json, encoding='utf-8')) if os.path.exists(region_json) else {}
    for s in syms:
        if s['cls'] in TAGGED_BY_REGION and s['id'] not in region:
            region[s['id']] = region_tag(reader, gray, s['bbox'], s['cls'])
            json.dump(region, open(region_json, 'w', encoding='utf-8'), ensure_ascii=False)
    # 도면 전체 OCR: 안쪽(문자 상자 절반 이상이 기호 안)과 주변(1.5배)
    used = set(); inside = {s['id']: [] for s in syms}; near = {s['id']: [] for s in syms}
    for i, t in enumerate(texts):
        best = max(syms, key=lambda s: overlap_ratio(t['box'], s['bbox']), default=None)
        if best and overlap_ratio(t['box'], best['bbox']) >= 0.5:
            inside[best['id']].append(t); used.add(i)
    for i, t in enumerate(texts):
        if i in used:
            continue
        cands = [s for s in syms if overlap_ratio(t['box'], expand(s['bbox'], NEAR_SCALE)) > 0]
        if cands:
            near[min(cands, key=lambda s: center_dist(t['box'], s['bbox']))['id']].append(t); used.add(i)
    for i, t in enumerate(texts):
        if i not in used and LINE_SPEC.search(t['text'].replace(' ', '')):
            line_rows.append([name, t['text'], round(t['conf'], 2)] + [round(v) for v in t['box']])
    valve_count = collections.Counter(region.get(s['id'], '') for s in syms if s['cls'] == 'valve')
    crop_dir = os.path.join(out_dir, 'crops', name); os.makedirs(crop_dir, exist_ok=True)
    rows = []
    for s in sorted(syms, key=lambda s: (s['bbox'][1], s['bbox'][0])):
        c = crop(gray, s['bbox'], NEAR_SCALE)
        cpath = os.path.join(crop_dir, f"{s['id']}.png")
        if c is not None:
            cv2.imwrite(cpath, c)
        tin, tnear = join_lines(inside[s['id']]), join_lines(near[s['id']])
        tbub = bub.get(s['id'], '') if s['cls'] == 'instrumentation' else ''
        treg = region.get(s['id'], '')
        sug = tbub or treg or tin or tnear
        bcand = b_candidate(tbub) if tbub else ''
        if s['cls'] == 'instrumentation' and tbub:
            trust = '높음' if large and not bcand else '확인 필요'
        else:
            trust = '확인 필요' if sug else ''
        dup = '중복' if s['cls'] == 'valve' and treg and valve_count[treg] > 1 else ''
        rows.append([name, s['id'], s['cls']] + [round(v, 1) for v in s['bbox']] +
                    [tin, tnear, tbub, treg, sug, bcand, trust, dup, '', os.path.relpath(cpath, out_dir)])
    with open(os.path.join(out_dir, f'{name}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['도면', '노드', '종류', 'xmin', 'ymin', 'xmax', 'ymax', '안쪽 문자', '주변 문자', '계기 원 OCR', '영역 태그',
                    '제안 태그', 'B 후보', '자동 신뢰', '중복', '확정 태그', '조각 이미지'])
        w.writerows(rows)
    by = collections.Counter(r[2] for r in rows); filled = collections.Counter(r[2] for r in rows if r[11])
    high = sum(1 for r in rows if r[13] == '높음')
    print(f"{name}: 기호 {len(rows)}, 제안 있음 {sum(filled.values())}, 자동 신뢰 높음 {high}, 계기 원 {bubble_h:.0f}px, "
          + ', '.join(f'{k} {filled[k]}/{by[k]}' for k in sorted(by)), flush=True)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root'); ap.add_argument('out'); ap.add_argument('--only', default='')
    ap.add_argument('--paddle-python', default=DEFAULT_PADDLE)
    a = ap.parse_args()
    order = a.only.split(',') if a.only else sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(a.root, '*.png')))
    plans = [(os.path.join(a.root, n + '.png'), os.path.join(a.root, n + '.graphml')) for n in order
             if os.path.exists(os.path.join(a.root, n + '.graphml'))]
    os.makedirs(a.out, exist_ok=True)
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    line_rows = []
    for png, gml in plans:
        annotate(png, gml, a.out, reader, a.paddle_python, line_rows)
    with open(os.path.join(a.out, 'lines.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['도면', '문자', '신뢰도', 'xmin', 'ymin', 'xmax', 'ymax'])
        w.writerows(line_rows)

if __name__ == '__main__':
    main()
