"""다중 추출 일치도: 같은 도면을 입력 배율·선 굵기·접점 허용치·간격 허용치를 바꿔 여러 번 추출하고,
기준 추출(표본 결과 graph.json)의 각 배관 연결이 변형 추출에서 몇 번 다시 나오는지 센다. 학습이 필요 없는 불확실성 신호.
래스터는 기준 추출의 문자 인식 결과(doc_ocr.json)를 좌표만 바꿔 재사용하므로 문자 인식을 다시 하지 않음.
사용: PYTHONPATH=../../app:../dexpi-reference-pid python consistency.py [도면 이름 일부]  → consistency/<도면>.json"""
import os, sys, json, math, tempfile, collections, copy
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PID = os.path.join(ROOT, 'examples', 'public-documents', 'pid')
sys.path.insert(0, PID); sys.path.insert(0, HERE)
import extract_graph as eg
import raster_graph as rg
from feasibility import DRAWINGS
SAMPLES = os.path.join(ROOT, 'examples', 'sample-inputs')
SRC = {  # 기준 추출 폴더 → (입력 파일, 종류)
    'pid-standard-vector': ('input/pid-standard-vector.svg', 'svg'), 'pid-standard-200dpi': ('output/pid-standard-200dpi/input_gray.png', 'png'),
    'pid-standard-scan': ('input/pid-standard-scan.png', 'png'), 'pid-plant-complex-vector': ('input/pid-plant-complex-vector.svg', 'svg'),
    'pid-plant-complex-150dpi': ('output/pid-plant-complex-150dpi/input_gray.png', 'png'), 'pid-lab-vector': ('input/pid-lab-vector.svg', 'svg'),
    'pid-c02-vector': (os.path.join(PID, 'input', 'C02.svg'), 'svg'), 'pid-c03-vector': (os.path.join(PID, 'input', 'C03.svg'), 'svg'),
}
# (이름, 배율, 선 굵기 변형(-1 침식·+1 팽창), 접점 허용치 배수, 간격 허용치 배수, 최소 선 길이 배수)
RASTER_VARIANTS = [('scale0.85', 0.85, 0, 1, 1, 1), ('scale1.15', 1.15, 0, 1, 1, 1), ('erode', 1, -1, 1, 1, 1), ('dilate', 1, 1, 1, 1, 1),
                   ('touch0.7', 1, 0, 0.7, 1, 1), ('touch1.4', 1, 0, 1.4, 1, 1), ('gap0.6', 1, 0, 1, 0.6, 1), ('gap1.5', 1, 0, 1, 1.5, 1),
                   ('long0.7', 1, 0, 1, 1, 0.7), ('long1.4', 1, 0, 1, 1, 1.4)]
VECTOR_VARIANTS = [v for v in RASTER_VARIANTS if v[1] == 1 and v[2] == 0]
BASE = dict(TOUCH=eg.TOUCH, GAP=eg.GAP, LONG=eg.LONG)

def lifted_pairs(g):
    nodes = {n['id']: n for n in g['nodes']}
    def lift(x):
        n = nodes.get(x)
        return n['attached_to'] if n and n.get('attached_to') else (n['annotates'] if n and n.get('annotates') else x)
    out = set()
    for r in g['runs']:
        if r['a'].startswith('open') or r['b'].startswith('open') or r['kind'] == 'signal':
            continue
        a, b = lift(r['a']), lift(r['b'])
        if a != b:
            out.add(tuple(sorted((a, b))))
    return out

def anchor(g, x):
    """요소·분기점의 위치(mm)."""
    for n in g['nodes']:
        if n['id'] == x:
            b = n['bbox']; return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), n['role']
    for j in g['junctions']:
        if j['id'] == x:
            return tuple(j['pt']), 'junction'
    return None, None

def mapper(base, var, tol=3.0):
    """변형 추출의 요소를 기준 추출의 요소로 대응. 요소는 같은 종류 중 상자 겹침(IoU 0.3 이상)이 가장 큰 것, 없으면 중심 거리 tol mm 안의 가장 가까운 것. 분기점은 거리 기준."""
    def iou(p, q):
        ix = max(0, min(p[2], q[2]) - max(p[0], q[0])); iy = max(0, min(p[3], q[3]) - max(p[1], q[1]))
        u = (p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - ix * iy
        return ix * iy / u if u > 0 else 0
    ctr = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    bnodes = [n for n in base['nodes'] if n['role'] not in ('mark', 'arrow')]
    vn = {n['id']: n for n in var['nodes']}; vj = {j['id']: j for j in var['junctions']}
    cache = {}
    def m(x):
        if x in cache:
            return cache[x]
        best = None
        if x in vn:
            n = vn[x]; same = [c for c in bnodes if c['role'] == n['role']] or bnodes
            sc = max(((iou(n['bbox'], c['bbox']), c['id']) for c in same), default=(0, None))
            if sc[0] >= 0.3:
                best = sc[1]
            else:
                d = [(math.dist(ctr(n['bbox']), ctr(c['bbox'])), c['id']) for c in same]
                d = [t for t in d if t[0] < tol]; best = min(d)[1] if d else None
        elif x in vj:
            d = [(math.dist(vj[x]['pt'], j['pt']), j['id']) for j in base['junctions']]
            d = [t for t in d if t[0] < tol]; best = min(d)[1] if d else None
        cache[x] = best; return best
    return m

def run_variant(kind, src, dpi, ocr, v, tmp):
    name, s, morph, tm, gm, lm = v
    eg.TOUCH, eg.GAP, eg.LONG = BASE['TOUCH'] * tm, BASE['GAP'] * gm, BASE['LONG'] * lm
    try:
        prefix = os.path.join(tmp, name)
        if kind == 'svg':
            return eg.main(src, prefix)
        im = cv2.imread(src, cv2.IMREAD_GRAYSCALE)
        if morph:
            k = np.ones((2, 2), np.uint8)
            im = cv2.dilate(im, k) if morph < 0 else cv2.erode(im, k)    # 흰 바탕 검은 선: 밝은 쪽 팽창 = 선 가늘게
        if s != 1:
            im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        png = prefix + '.png'; cv2.imwrite(png, im)
        o = [[[[x * s, y * s] for x, y in q], t, c] for q, t, c in ocr]
        oj = prefix + '_ocrin.json'; json.dump(o, open(oj, 'w'))
        return rg.main(png, int(round(dpi * s)), prefix, ocr_json=oj)
    finally:
        eg.TOUCH, eg.GAP, eg.LONG = BASE['TOUCH'], BASE['GAP'], BASE['LONG']

def main(only=''):
    os.makedirs(os.path.join(HERE, 'consistency'), exist_ok=True)
    for name, gp, xml, grp in DRAWINGS:
        stem = os.path.basename(os.path.dirname(gp))
        if only and only not in stem:
            continue
        base = json.load(open(gp, encoding='utf-8'))
        rel, kind = SRC[stem]
        src = rel if os.path.isabs(rel) else os.path.join(SAMPLES, rel)
        dpi = ocr = None
        if kind == 'png':
            R = json.load(open(os.path.join(os.path.dirname(gp), 'result.json'), encoding='utf-8'))
            dpi = R['dpi']; ocr = json.load(open(os.path.join(os.path.dirname(gp), 'doc_ocr.json')))
            if stem == 'pid-standard-scan':      # 기준 추출과 같은 기울기 보정 영상을 만듦(문자 좌표가 이 영상 기준)
                g0 = cv2.imread(src, cv2.IMREAD_GRAYSCALE); g0, _ = rg.deskew(g0)
                src = os.path.join(tempfile.gettempdir(), 'scan_gray.png'); cv2.imwrite(src, g0)
        bp = lifted_pairs(base)
        counts = collections.Counter(); runs = []
        variants = VECTOR_VARIANTS if kind == 'svg' else RASTER_VARIANTS
        with tempfile.TemporaryDirectory() as tmp:
            import contextlib, io
            for v in variants:
                with contextlib.redirect_stdout(io.StringIO()):
                    g = run_variant(kind, src, dpi, ocr, v, tmp)
                m = mapper(base, g)
                vp = {tuple(sorted((m(a), m(b)))) for a, b in lifted_pairs(g) if m(a) and m(b) and m(a) != m(b)}
                for p in bp:
                    counts[p] += p in vp
                runs.append(dict(variant=v[0], pairs=len(lifted_pairs(g)), kept=sum(p in vp for p in bp)))
        out = dict(drawing=name, n_variants=len(variants), base_pairs=len(bp), runs=runs,
                   agree={f'{a}|{b}': counts[(a, b)] / len(variants) for a, b in sorted(bp)})
        json.dump(out, open(os.path.join(HERE, 'consistency', f'{stem}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(name, len(bp), [(r['variant'], r['kept']) for r in runs], flush=True)

if __name__ == '__main__':
    main(*sys.argv[1:])
