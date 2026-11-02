"""추출 연결 검증 주제의 사전 판정. 기존 추출 그래프의 배관 연결마다 정답 여부를 붙이고, 검토 순서를 정하는 점수들이 틀린 연결을 얼마나 앞쪽에 모으는지 잰다.
점수
  random    무작위(씨앗 20회 평균)
  gap       끝점 간격(열린 끝을 이어 붙인 거리)이 큰 연결부터
  topo      위상·도메인 제약 위반 수(학습 없음) + 간격
  lr        특징 전체의 로지스틱 회귀, 도면 단위 교차 검증(평가 도면은 학습에서 뺌)
지표: 틀린 연결 검출 AUC, 검토 예산(전체 연결의 10·20·30%) 안에서 찾은 틀린 연결 비율(오류 재현율@k)
사용: python feasibility.py  → result.md"""
import os, sys, json, math, random, collections, re
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PID = os.path.join(ROOT, 'examples', 'public-documents', 'pid')
sys.path.insert(0, PID)
import evaluate as ev
from shapely.geometry import box, Point, LineString

S = os.path.join(ROOT, 'examples', 'sample-inputs', 'output'); D = os.path.join(ROOT, 'examples', 'llm-qa', 'docs'); X = os.path.join(PID, 'input')
DRAWINGS = [  # (이름, 그래프, 정답 XML, 도면 묶음: 같은 원본의 다른 렌더링은 같은 묶음)
    ('C01 벡터', f'{S}/pid-standard-vector/graph.json', f'{X}/C01V04-VER.EX01.xml', 'C01'),
    ('C01 200dpi', f'{S}/pid-standard-200dpi/graph.json', f'{X}/C01V04-VER.EX01.xml', 'C01'),
    ('C01 스캔', f'{S}/pid-standard-scan/graph.json', f'{X}/C01V04-VER.EX01.xml', 'C01'),
    ('C02 벡터', f'{D}/pid-c02-vector/graph.json', f'{X}/C02V03-VER.EX02.xml', 'C02'),
    ('C03 벡터', f'{D}/pid-c03-vector/graph.json', f'{X}/C03V04-VER.EX02.xml', 'C03'),
    ('증류 플랜트 벡터', f'{S}/pid-plant-complex-vector/graph.json', f'{X}/distillation_plant.xml', 'DP'),
    ('증류 플랜트 150dpi', f'{S}/pid-plant-complex-150dpi/graph.json', f'{X}/distillation_plant.xml', 'DP'),
    ('증류 실험실 벡터', f'{S}/pid-lab-vector/graph.json', f'{X}/distillation_laboratory.xml', 'DL'),
]

def labelled_pairs(g, xml):
    """evaluate.main과 같은 대응 규칙으로 추출 인접 쌍마다 정답(1)·오류(0)·신호선(None)을 붙이고 쌍을 만든 구간 목록을 돌려줌."""
    comps, conns, _ = ev.load_gt(xml, g['page'][1])
    nodes = {n['id']: n for n in g['nodes']}
    def lift(nid):
        n = nodes.get(nid)
        if n and n.get('attached_to'):
            return n['attached_to']
        if n and n.get('annotates'):
            return n['annotates']
        return nid
    def match_point(pt, tol=1.5):
        best, bd = None, tol
        for n in g['nodes']:
            if n['role'] in ('arrow', 'mark'):
                continue
            d = box(*n['bbox']).distance(Point(pt))
            if d < bd:
                best, bd = n['id'], d
        for j in g['junctions']:
            d = math.dist(j['pt'], pt)
            if d < bd:
                best, bd = j['id'], d
        return best
    gt2ex = {}
    for cid, c in comps.items():
        if c['kind'] in ('PipingNetworkSegment', 'PipingNetworkSystem', 'ActuatingSystem'):
            continue
        hits = [h for h in (match_point(p) for p in ([c['pos']] if c['pos'] else []) + c['nodes']) if h]
        if hits:
            gt2ex[cid] = lift(collections.Counter(hits).most_common(1)[0][0])
    nosym = {k for k, c in comps.items() if c.get('nosym') and ev.entity(comps, k) == k}
    run_geoms = [LineString(r['coords']) for r in g['runs'] if len(r['coords']) >= 2]
    passthrough = {k for k, c in comps.items() if c['kind'] == 'PipingComponent' and k not in gt2ex and c['pos'] and k not in nosym
                   and any(rg.distance(Point(c['pos'])) < 1.5 for rg in run_geoms)}
    gt_pairs = {p for p in ev.gt_adjacency(comps, conns, skip=passthrough) if not (set(p) & nosym)}
    ex2gt = collections.defaultdict(set)
    for k, v in gt2ex.items():
        ex2gt[v].add(k)
    pairs = collections.defaultdict(list)
    for r in g['runs']:
        a, b = r['a'], r['b']
        if a.startswith('open') or b.startswith('open'):
            continue
        a, b = lift(a), lift(b)
        if a != b:
            pairs[tuple(sorted((a, b)))].append(r)
    out = {}
    for (a, b), rs in pairs.items():
        roles = {nodes[x]['role'] for x in (a, b) if x in nodes}
        if any(r['kind'] == 'signal' for r in rs) or 'instrument' in roles:
            out[(a, b)] = (None, rs); continue
        cand = {tuple(sorted((x, y))) for x in ex2gt.get(a, set()) for y in ex2gt.get(b, set())}
        out[(a, b)] = (1 if cand & gt_pairs else 0, rs)
    return out, nodes, lift

DN = re.compile(r'DN=(\d+)'); LINE = re.compile(r'라인=(\S+)')
def run_line_fields(r):
    import serialize as sz
    f = sz.line_fields(r['texts']) if r['texts'] else ''
    m1, m2 = DN.search(f), LINE.search(f)
    return (m1.group(1) if m1 else None), (m2.group(1) if m2 else None)

def features(g, pairs, nodes, lift):
    """쌍마다 특징 벡터. 기하(간격·길이·꺾임·굵기)와 위상·도메인 제약(차수, 분기점 차수, 2구 부품 차수 초과, 장비 노즐 수 초과, 라벨 DN 모순, 막다른 끝, 같은 쌍 중복)."""
    pipe = [(k, v) for k, v in pairs.items() if v[0] is not None]
    deg = collections.Counter()
    for (a, b), (_, rs) in pairs.items():
        deg[a] += 1; deg[b] += 1
    juncs = {j['id'] for j in g['junctions']}
    # 각 요소에 붙은 연결의 DN 라벨 모음
    dn_at = collections.defaultdict(set)
    for (a, b), (_, rs) in pairs.items():
        for r in rs:
            dn, _ = run_line_fields(r)
            if dn:
                dn_at[a].add(dn); dn_at[b].add(dn)
    widths = [r['width'] for (_, (_, rs)) in pairs.items() for r in rs if r.get('width')]
    w_main = float(np.median(widths)) if widths else 1.0
    def noz(n):
        return sum(1 for t in n['texts'] if re.match(r'^N[0-9I]{1,2}$', t))
    F, y, names = [], [], []
    for (a, b), (lab, rs) in pipe:
        gap = max(r.get('gap') or 0 for r in rs)
        length = sum(LineString(r['coords']).length for r in rs if len(r['coords']) >= 2)
        bends = max(len(r['coords']) - 2 for r in rs)
        wdev = max(abs((r.get('width') or w_main) - w_main) / w_main for r in rs)
        dashed = any(r.get('dashed') for r in rs)
        labelled = any(r['texts'] for r in rs)
        viol = 0
        for x in (a, b):
            n = nodes.get(x)
            if x in juncs and deg[x] < 3:
                viol += 1                                   # 분기점인데 연결 2개 이하
            if n and n['role'] == 'symbol' and deg[x] > 2:
                viol += 1                                   # 2구 부품(밸브 등)인데 연결 3개 이상
            if n and n['role'] == 'equipment' and noz(n) and deg[x] > noz(n):
                viol += 1                                   # 장비 연결 수가 노즐 수 초과
            if deg[x] == 1 and (n is None or n['role'] not in ('equipment',)):
                viol += 1                                   # 장비가 아닌 막다른 끝
        dn_conf = int(any(len(dn_at[x]) > 2 for x in (a, b)))   # 한 요소에 서로 다른 DN이 셋 이상
        dup = int(len(rs) > 1)
        f = [math.log1p(gap), int(gap > 0), math.log1p(length), bends, wdev, int(dashed), int(labelled), viol, dn_conf, dup,
             int(a in juncs or b in juncs), int(any(nodes.get(x, {}).get('role') == 'equipment' for x in (a, b)))]
        F.append(f); y.append(1 - lab); names.append((a, b))      # y=1이 틀린 연결
    return np.array(F, float), np.array(y, int), names

FEAT = ['log 간격', '간격 있음', 'log 길이', '꺾임 수', '굵기 편차', '점선', '라벨 있음', '제약 위반 수', 'DN 모순', '같은 쌍 중복', '분기점 포함', '장비 포함']

def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    if not len(pos) or not len(neg):
        return float('nan')
    s = 0.0
    for p in pos:
        s += (neg < p).sum() + 0.5 * (neg == p).sum()
    return s / (len(pos) * len(neg))

def recall_at(score, y, frac, rnd=None):
    n = max(1, int(round(frac * len(y))))
    order = np.lexsort((rnd.random(len(y)) if rnd is not None else np.zeros(len(y)), -score))
    return y[order[:n]].sum() / max(1, y.sum())

def fit_lr(X, y, l2=1.0, it=500, lr=0.1):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = (X - mu) / sd; w = np.zeros(Z.shape[1]); b = 0.0
    for _ in range(it):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        w -= lr * (Z.T @ (p - y) / len(y) + l2 * w / len(y)); b -= lr * (p - y).mean()
    return lambda Xn: ((Xn - mu) / sd) @ w + b, w

def main():
    data = []
    for name, gp, xml, grp in DRAWINGS:
        g = json.load(open(gp, encoding='utf-8'))
        pairs, nodes, lift = labelled_pairs(g, xml)
        Fx, y, nm = features(g, pairs, nodes, lift)
        data.append((name, grp, Fx, y))
    groups = sorted({d[1] for d in data})
    rows = []; allsc = collections.defaultdict(list); ally = []
    for name, grp, Fx, y in data:
        train = [d for d in data if d[1] != grp]                     # 같은 원본 도면의 렌더링은 학습에서 모두 뺌
        Xt = np.vstack([d[2] for d in train]); yt = np.concatenate([d[3] for d in train])
        pred, _ = fit_lr(Xt, yt)
        sc = dict(gap=Fx[:, 0], topo=Fx[:, 7] + Fx[:, 8] + 0.5 * Fx[:, 1] + 0.1 * Fx[:, 0], lr=pred(Fx))
        rnd = np.random.default_rng(0)
        r = dict(name=name, n=len(y), err=int(y.sum()))
        r['random'] = {k: np.mean([recall_at(rnd.random(len(y)), y, k) for _ in range(20)]) for k in (0.1, 0.2, 0.3)}
        r['random_auc'] = 0.5
        for k, s in sc.items():
            r[k + '_auc'] = auc(s, y); r[k] = {f: recall_at(s, y, f, np.random.default_rng(1)) for f in (0.1, 0.2, 0.3)}
            allsc[k].append(s)
        ally.append(y); rows.append(r)
    _, w = fit_lr(np.vstack([d[2] for d in data]), np.concatenate([d[3] for d in data]))
    L = ['# 추출 연결 검증 사전 판정', '', '틀린 연결 = 정답 대조에서 오류로 판정된 배관 인접 쌍(신호선 쌍 제외). 오류 재현율@20% = 연결 20%를 검토했을 때 찾은 틀린 연결의 비율.', '',
         '| 도면 | 연결 | 틀린 연결 | AUC gap | AUC topo | AUC lr | @20% 무작위 | @20% gap | @20% topo | @20% lr |', '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        L.append(f"| {r['name']} | {r['n']} | {r['err']} | {r['gap_auc']:.2f} | {r['topo_auc']:.2f} | {r['lr_auc']:.2f} | {r['random'][0.2]:.2f} | {r['gap'][0.2]:.2f} | {r['topo'][0.2]:.2f} | {r['lr'][0.2]:.2f} |")
    valid = [r for r in rows if r['err'] and r['err'] < r['n']]
    for k in ('gap', 'topo', 'lr'):
        L.append(f"\n{k}: 도면 평균 AUC {np.nanmean([r[k + '_auc'] for r in valid]):.3f}, 오류 재현율@10/20/30% " +
                 ' / '.join(f"{np.mean([r[k][f] for r in valid]):.2f}" for f in (0.1, 0.2, 0.3)))
    L.append(f"\nrandom: 오류 재현율@10/20/30% " + ' / '.join(f"{np.mean([r['random'][f] for r in valid]):.2f}" for f in (0.1, 0.2, 0.3)))
    L += ['', '## 전체 자료로 학습한 로지스틱 회귀 계수(표준화, 양수 = 틀린 연결 쪽)', '', '| 특징 | 계수 |', '|---|---|'] + [f"| {n} | {v:+.2f} |" for n, v in zip(FEAT, w)]
    open(os.path.join(HERE, 'result.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n'); print('\n'.join(L))

if __name__ == '__main__':
    main()
