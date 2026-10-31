"""raster_graph.py가 만든 graph.json을 PID2Graph 정답(truth.json)과 대조한다.

정답 기호는 상자가 가장 많이 겹치는 추출 노드에 대응시킨다(노즐·주석은 소속 요소로 올림).
추출 쪽은 배관 구간 양 끝을 노드로 올리고 분기점을 통과시켜 요소 간 인접 쌍을 만든다.
배관 정답 쌍 중 복원된 비율을 재현율로 적는다.
"""
import sys, json, math, collections
from shapely.geometry import box

def lift(nodes, nid):
    n = nodes.get(nid)
    if n and n.get('attached_to'):
        return n['attached_to']
    if n and n.get('annotates'):
        return n['annotates']
    return nid

def extracted_pairs(g):
    nodes = {n['id']: n for n in g['nodes']}
    adj = collections.defaultdict(set)
    for r in g['runs']:
        a, b = r['a'], r['b']
        if a.startswith('open') or b.startswith('open'):
            continue
        a, b = lift(nodes, a), lift(nodes, b)
        if a != b:
            adj[a].add((b, r['kind'])); adj[b].add((a, r['kind']))
    junc = {j['id'] for j in g['junctions']}
    pairs = {}
    for s in adj:
        if s in junc:
            continue
        stack = [(s, 'pipe', frozenset([s]))]
        while stack:
            cur, kind, seen = stack.pop()
            for nxt, k in adj[cur]:
                if nxt in seen:
                    continue
                kk = 'signal' if 'signal' in (kind, k) else 'pipe'
                if nxt in junc:
                    stack.append((nxt, kk, seen | {nxt}))
                elif nxt != s:
                    key = tuple(sorted((s, nxt)))
                    pairs[key] = 'signal' if pairs.get(key) == 'signal' or kk == 'signal' else 'pipe'
    return pairs, nodes

def match_symbols(truth, g, k):
    """정답 기호(픽셀)를 추출 노드(mm)에 대응. 겹침 넓이가 가장 큰 노드, 없으면 중심이 2 mm 안에 든 노드."""
    nodes = {n['id']: n for n in g['nodes']}
    cand = [(n['id'], box(*n['bbox'])) for n in g['nodes'] if n['role'] not in ('arrow', 'mark')]
    gt2ex = {}
    for s in truth['symbols']:
        gb = box(*[v * k for v in s['bbox']])
        best, ba = None, 0.0
        for nid, nb in cand:
            a = gb.intersection(nb).area
            if a > ba:
                best, ba = nid, a
        if best is None or ba < 0.2 * gb.area:
            c = gb.centroid
            near = [(nb.distance(c), nid) for nid, nb in cand]
            if near:
                d, nid = min(near)
                best = nid if d <= 2.0 else None
        if best:
            gt2ex[s['id']] = lift(nodes, best)
    return gt2ex

def evaluate(graph_json, truth_json, dpi, out_md=None):
    g = json.load(open(graph_json)); truth = json.load(open(truth_json))
    k = 25.4 / dpi
    gt2ex = match_symbols(truth, g, k)
    ex_pairs, nodes = extracted_pairs(g)
    rows, hit, merged = [], 0, 0
    gt_pipe = [p for p in truth['pairs'] if p['kind'] == 'pipe']
    for p in gt_pipe:
        ea, eb = gt2ex.get(p['a']), gt2ex.get(p['b'])
        ok = ea is not None and eb is not None and tuple(sorted((ea, eb))) in ex_pairs
        same = ea is not None and ea == eb
        hit += ok; merged += (same and not ok)
        rows.append((p['a'], p['b'], ea, eb, 'O' if ok else ('병합' if same else 'X')))
    ex2gt = collections.defaultdict(set)
    for a, b in gt2ex.items():
        ex2gt[b].add(a)
    gt_keys = {(p['a'], p['b']) for p in truth['pairs']}
    extra = 0
    for (a, b), kind in ex_pairs.items():
        if kind != 'pipe':
            continue
        cand = {tuple(sorted((x, y))) for x in ex2gt.get(a, ()) for y in ex2gt.get(b, ())}
        if not (cand & gt_keys):
            extra += 1
    n_ex_pipe = sum(1 for v in ex_pairs.values() if v == 'pipe')
    res = dict(symbols=len(truth['symbols']), symbols_matched=len(gt2ex), gt_pipe_pairs=len(gt_pipe), hit=hit, merged=merged,
               recall=round(hit / max(1, len(gt_pipe)), 3), ex_pipe_pairs=n_ex_pipe, extra=extra,
               precision=round((n_ex_pipe - extra) / max(1, n_ex_pipe), 3), dpi=dpi)
    if out_md:
        with open(out_md, 'w', encoding='utf-8') as f:
            f.write("# 정답 대조 결과\n\n")
            f.write(f"정답 기호 {res['symbols']}개 중 추출 노드에 대응된 기호 {res['symbols_matched']}개. ")
            f.write(f"배관 정답 쌍 {res['gt_pipe_pairs']}개 중 {hit}개 복원(재현율 {res['recall']:.2f}), 한 노드로 합쳐진 쌍 {merged}개. ")
            f.write(f"추출 배관 쌍 {n_ex_pipe}개 중 정답에 없는 쌍 {extra}개(정밀도 {res['precision']:.2f}).\n\n")
            f.write("| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |\n|---|---|---|---|---|\n")
            for r in rows:
                f.write("| " + " | ".join(str(x) for x in r) + " |\n")
    return res

if __name__ == '__main__':
    r = evaluate(sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else None)
    print(json.dumps(r, ensure_ascii=False))
