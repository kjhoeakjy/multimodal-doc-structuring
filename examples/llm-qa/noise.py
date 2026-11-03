"""추출 오류 통제 실험의 문맥 생성.
정답과 일치하는 C01 벡터 추출 그래프(배관 연결 재현율·정밀도 1.00)에 오류를 일정 비율로 넣고 같은 직렬화로 문맥을 만든다.
오류 종류
  drop   배관·신호 연결 간선을 비율 p만큼 지움(재현율 감소)
  add    가까운 요소 쌍 사이에 없는 연결을 기존 간선 수의 비율 p만큼 더함(정밀도 감소)
  label  선 라벨(라인 번호·유체·등급·DN)을 비율 p만큼 다른 선과 맞바꿈(라벨 오귀속)
  split  배관 간선 비율 p의 중간에 연결 둘인 분기점을 넣어 두 간선으로 나눔(래스터에서 관찰한 꺾임 분할)
  merge  가까운 기호(밸브 등) 쌍을 비율 p만큼 한 노드로 합침(요소 병합)
  node   기호·계기·노즐 노드를 비율 p만큼 지움(요소 누락. 붙은 선은 끊김. 실제 래스터에서 작은 기호를 못 찾는 오류를 본뜸)
  mix    drop과 ocr을 같은 비율로 함께 넣음(두 오류의 효과가 독립적으로 곱해지는지 확인)
  ocr    요소·선에 붙은 문자 토큰을 비율 p만큼 문자 인식 오류처럼 바꿈(8→B, 5→S, 0→D, 1→l, 2→Z, 끝 글자 누락 등. 실제 래스터에서 H1008→S8 같은 오독을 본뜸)
각 그래프는 DEXPI XML 정답과 다시 대조해 실제 재현율·정밀도를 기록한다(public-documents/pid/evaluate.py).
사용: python noise.py [--levels 0,0.1,0.2,0.3,0.5] [--seeds 0,1,2]
실제 추출 그래프(C01 200 dpi 래스터, 스캔)도 real-200dpi, real-scan 설정으로 넣어 통제 오류 곡선과 대조한다.
결과: noise/contexts.json(문항 id·오류 종류·비율·씨앗별 relations, full 문맥), noise/graphs.md(실제 재현율·정밀도·요소 문자 복원율)
실행: python run_noise.py --backend ollama --model <모델> --label <결과 이름>"""
import os, sys, json, math, random, argparse, tempfile, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'app'))
sys.path.insert(0, os.path.join(ROOT, 'examples', 'public-documents', 'pid'))
import pipeline as pl          # noqa: F401  (경로 설정과 같은 serialize 모듈 사용)
import serialize as sz
import evaluate as ev
from contexts import ablate

DOC = 'pid-standard-vector'
GRAPH = os.path.join(ROOT, 'examples', 'sample-inputs', 'output', DOC, 'graph.json')
XML = os.path.join(ROOT, 'examples', 'public-documents', 'pid', 'input', 'C01V04-VER.EX01.xml')
OUT = os.path.join(HERE, 'noise')
REAL = ('pid-standard-200dpi', 'pid-standard-scan')     # 같은 도면의 실제 규칙 기반 추출 결과

def center(n):
    b = n['bbox']; return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

CONFUSE = {'0': 'D', '1': 'l', '2': 'Z', '4': 'A', '5': 'S', '6': 'G', '7': 'T', '8': 'B', '9': 'g', 'O': 'Q', 'I': 'l', 'B': '8', 'S': '5', 'H': 'N', 'K': 'X', 'P': 'F', 'T': 'I'}

def misread(tok, rnd):
    """문자 인식 오류 하나를 흉내 냄: 글자 하나 혼동(절반), 끝 글자 누락, 글자 하나 삽입"""
    cand = [i for i, ch in enumerate(tok) if ch in CONFUSE]
    r = rnd.random()
    if cand and r < 0.6:
        i = rnd.choice(cand); return tok[:i] + CONFUSE[tok[i]] + tok[i + 1:]
    if len(tok) > 2 and r < 0.85:
        return tok[:-1]
    i = rnd.randrange(len(tok) + 1); return tok[:i] + rnd.choice('l1I|') + tok[i:]

def perturb(g, kind, p, seed):
    g = json.loads(json.dumps(g)); rnd = random.Random(seed)
    if kind == 'mix':
        return perturb(perturb(g, 'drop', p, seed), 'ocr', p, seed + 100)
    if kind == 'node':
        cand = [n for n in g['nodes'] if n['role'] in ('symbol', 'instrument') or n.get('attached_to')]
        gone = {n['id'] for n in rnd.sample(cand, int(round(p * len(cand))))}
        g['nodes'] = [n for n in g['nodes'] if n['id'] not in gone]
        g['runs'] = [r for r in g['runs'] if r['a'] not in gone and r['b'] not in gone]
        for n in g['nodes']:
            if n.get('annotates') in gone:
                n['annotates'] = None
        return g
    if kind == 'ocr':
        slots = [(n['texts'], i) for n in g['nodes'] if n['role'] != 'note' for i in range(len(n['texts']))] + [(r['texts'], i) for r in g['runs'] for i in range(len(r['texts']))]
        for texts, i in rnd.sample(slots, int(round(p * len(slots)))):
            texts[i] = ' '.join(misread(t, rnd) if rnd.random() < 0.7 else t for t in texts[i].split()) if ' ' in texts[i] else misread(texts[i], rnd)
        return g
    runs = [r for r in g['runs'] if r['kind'] in ('pipe', 'signal')]
    k = int(round(p * len(runs)))
    if kind == 'drop' and k:
        gone = {r['id'] for r in rnd.sample(runs, k)}
        g['runs'] = [r for r in g['runs'] if r['id'] not in gone]
    elif kind == 'add' and k:
        cand = [n for n in g['nodes'] if n['role'] in ('equipment', 'symbol', 'instrument') and not n.get('attached_to')]
        have = {frozenset((r['a'], r['b'])) for r in g['runs']}
        pairs = []
        for i, a in enumerate(cand):     # 실제 오류처럼 가까운 요소 사이에 생기는 거짓 연결: 각 요소의 가까운 이웃 5개 안에서 고름
            near = sorted(cand[:i] + cand[i + 1:], key=lambda b: math.dist(center(a), center(b)))[:5]
            pairs += [(a, b) for b in near if frozenset((a['id'], b['id'])) not in have]
        rnd.shuffle(pairs); used = set()
        for a, b in pairs:
            if k == 0:
                break
            key = frozenset((a['id'], b['id']))
            if key in used:
                continue
            used.add(key); k -= 1
            ca, cb = center(a), center(b)
            g['runs'].append(dict(id=f"r{len(g['runs']) + 900}", a=a['id'], b=b['id'], coords=[list(ca), [cb[0], ca[1]], list(cb)],
                                  width=0.5, dashed=False, kind='pipe', gap=0, arrows=[], texts=[]))
    elif kind == 'label' and k:
        lab = [r for r in g['runs'] if r['texts']]
        pick = rnd.sample(lab, min(len(lab), max(2, k)))
        texts = [r['texts'] for r in pick]
        rnd.shuffle(texts)
        if len(pick) > 1 and all(t is r['texts'] for t, r in zip(texts, pick)):
            texts = texts[1:] + texts[:1]
        for r, t in zip(pick, texts):
            r['texts'] = t
    elif kind == 'split' and k:
        for r in rnd.sample([r for r in runs if r['kind'] == 'pipe'], min(k, sum(r['kind'] == 'pipe' for r in runs))):
            (x0, y0), (x1, y1) = r['coords'][0], r['coords'][-1]
            mid = [(x0 + x1) / 2, (y0 + y1) / 2]; jid = f"j{len(g['junctions']) + 900}"
            g['junctions'].append(dict(id=jid, pt=mid))
            g['runs'].append(dict(r, id=f"r{len(g['runs']) + 900}", a=jid, coords=[mid, [x1, y1]], texts=[]))
            r['b'] = jid; r['coords'] = [[x0, y0], mid]
    elif kind == 'merge' and k:
        syms = [n for n in g['nodes'] if n['role'] == 'symbol' and not n.get('attached_to')]
        pairs = sorted(((math.dist(center(a), center(b)), a['id'], b['id']) for i, a in enumerate(syms) for b in syms[i + 1:]))
        n_merge = max(1, int(round(p * len(syms) / 2))); gone = set(); done = 0
        for _, a, b in pairs:
            if done >= n_merge:
                break
            if a in gone or b in gone:
                continue
            gone |= {a, b}; done += 1
            na = next(n for n in g['nodes'] if n['id'] == a); nb = next(n for n in g['nodes'] if n['id'] == b)
            na['bbox'] = [min(na['bbox'][0], nb['bbox'][0]), min(na['bbox'][1], nb['bbox'][1]), max(na['bbox'][2], nb['bbox'][2]), max(na['bbox'][3], nb['bbox'][3])]
            na['texts'] = na['texts'] + nb['texts']
            for r in g['runs']:
                r['a'] = a if r['a'] == b else r['a']; r['b'] = a if r['b'] == b else r['b']
            g['runs'] = [r for r in g['runs'] if r['a'] != r['b']]
            g['nodes'] = [n for n in g['nodes'] if n['id'] != b]
    return g

def serial_of(g):
    with tempfile.TemporaryDirectory() as d:
        gp = os.path.join(d, 'g.json'); tp = os.path.join(d, 'g.txt')
        json.dump(g, open(gp, 'w', encoding='utf-8'), ensure_ascii=False)
        sz.main(gp, tp)
        lines = open(tp, encoding='utf-8').read().rstrip('\n').split('\n')
        mp = os.path.join(d, 'e.md'); ev.main(gp, XML, mp)
        s = open(mp, encoding='utf-8').read()
    m = re.search(r'정답 인접 쌍 (\d+)개 중 (\d+)개 복원.*?추출 인접 쌍 (\d+)개 중 정답에 없는 쌍 (\d+)개\. 이 중 (\d+)개는', s, re.S)
    gt, rec, ex, extra, sig = map(int, m.groups())
    return lines, dict(recall=rec / gt, precision=(ex - extra) / max(1, ex - sig), label=text_recall(g))

_GT_TEXTS = None
def text_recall(g):
    """정답 XML의 요소 문자(장비·부품·계기·노즐 소속 Text) 가운데 그래프의 문자 토큰에 그대로 있는 비율. 문자 오독 오류와 실제 추출의 문자 인식 손실을 같은 잣대로 잼"""
    global _GT_TEXTS
    if _GT_TEXTS is None:
        comps, _, labels = ev.load_gt(XML, 297.053)
        _GT_TEXTS = [l['text'] for l in labels if l['owner'] in comps and comps[l['owner']]['kind'] in ('Equipment', 'Nozzle', 'PipingComponent', 'ProcessInstrumentationFunction')
                     and re.fullmatch(r'[A-Z0-9.\-]+', l['text'])]     # 식별자 형태(장비 태그, 노즐 번호, 호칭 지름, 밸브·계기 번호)만. 장비 데이터 표의 문구는 제외
    toks = set()
    for n in g['nodes']:
        toks |= {t for x in n['texts'] for t in x.split()} | set(n['texts'])
    for r in g['runs']:
        toks |= {t for x in r['texts'] for t in x.split()} | set(r['texts'])
    toks |= {t.replace('O', '0').replace('I', '1') for t in toks}
    return sum(t in toks for t in _GT_TEXTS) / max(1, len(_GT_TEXTS))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--levels', default='0,0.1,0.2,0.3,0.5'); ap.add_argument('--seeds', default='0,1,2')
    a = ap.parse_args()
    levels = [float(x) for x in a.levels.split(',')]; seeds = [int(x) for x in a.seeds.split(',')]
    g0 = json.load(open(GRAPH, encoding='utf-8'))
    Q = [q for q in json.load(open(os.path.join(HERE, 'questions.json'), encoding='utf-8')) if q['doc'] == DOC]
    os.makedirs(OUT, exist_ok=True)
    ctx, rows = {}, []
    for kind in ('drop', 'add', 'label', 'split', 'merge', 'ocr', 'node', 'mix'):
        for p in levels:
            for s in (seeds if p > 0 else [0]):
                if p == 0 and kind != 'drop':
                    continue
                key = f"{kind if p > 0 else 'none'}-{p:g}-s{s}"
                lines, m = serial_of(perturb(g0, kind, p, s))
                rows.append((key, m))
                ctx[key] = {c: ablate(lines, c, True) for c in ('relations', 'full')}
    for real in REAL:     # 실제 추출 그래프(래스터·스캔)도 같은 문항으로 묻기 위해 같은 형식으로 넣음
        key = f"real-{real.split('-')[-1]}-s0"
        lines, m = serial_of(json.load(open(os.path.join(ROOT, 'examples', 'sample-inputs', 'output', real, 'graph.json'), encoding='utf-8')))
        rows.append((key, m))
        ctx[key] = {c: ablate(lines, c, True) for c in ('relations', 'full')}
    json.dump(dict(doc=DOC, questions=[q['id'] for q in Q], contexts=ctx), open(os.path.join(OUT, 'contexts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    L = ['# 오류를 넣은 C01 그래프의 실제 배관 연결 재현율·정밀도', '', f'문항 {len(Q)}(C01 벡터). 정답 대조는 DEXPI XML.', '', '| 조건 | 재현율 | 정밀도 | 문자 복원 |', '|---|---|---|---|']
    L += [f"| {k} | {m['recall']:.2f} | {m['precision']:.2f} | {m['label']:.2f} |" for k, m in rows]
    open(os.path.join(OUT, 'graphs.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    main()
