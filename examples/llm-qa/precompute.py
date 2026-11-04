"""그래프에서 연결 의존 정보를 미리 계산해 문맥 줄로 만든다(절차 계층). 모델이 연결을 스스로 따라가지 못하는 문항(경로·라인 경로·라인 도달·연결 수)의 답 근거를 코드로 준비함.
도달 규칙은 직렬화의 '장비 간 배관 연결'과 같음(배관·신호 연결을 모두 따르고 분기점·밸브·기호·계기는 지나며 장비에서 멈춤).
make_conn_questions.py가 같은 함수로 문항을 만들므로, 오류 없는 그래프에서는 미리 계산한 줄이 정답과 일치하고 오류가 든 그래프에서는 오류가 그대로 전파됨."""
import re, itertools, collections
import serialize as sz

def build(g):
    nodes = {n['id']: n for n in g['nodes']}
    def lift(nid):
        n = nodes.get(nid); return n['attached_to'] if n and n.get('attached_to') else nid
    adj = collections.defaultdict(set); deg = collections.Counter()
    for r in g['runs']:
        a, b = lift(r['a']), lift(r['b'])
        if a == b:
            continue
        adj[a].add(b); adj[b].add(a)
        for v in (a, b):
            if v in nodes and nodes[v]['role'] == 'equipment':
                deg[v] += 1
    equip = {n['id']: sz.name_of(n) for n in g['nodes'] if n['role'] == 'equipment' and not n.get('attached_to')}
    return nodes, adj, deg, equip, lift

def reach_from(starts, adj, equip):
    """starts에서 출발해 장비에서 멈추는 도달. 출발점이 장비면 그 장비는 답에서 뺌."""
    seen, frontier, out = set(starts), list(starts), set()
    while frontier:
        nxt = []
        for v in frontier:
            for w in adj[v]:
                if w in seen:
                    continue
                seen.add(w)
                if w in equip:
                    out.add(w)
                else:
                    nxt.append(w)
        frontier = nxt
    return out

def shortest_inner(a, b, adj, equip):
    """장비 a에서 b까지 다른 장비를 지나지 않는 최단 경로의 중간 요소 수. 없으면 None."""
    prev, frontier = {a: None}, [a]
    while frontier:
        nxt = []
        for v in frontier:
            for w in sorted(adj[v]):
                if w in prev:
                    continue
                prev[w] = v
                if w == b:
                    path = [w]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return len(path) - 2
                if w not in equip:
                    nxt.append(w)
        frontier = nxt
    return None

def line_numbers(g, lift):
    """라인 번호 → 그 선의 양 끝 요소, 요소 쌍 → 그 사이 선의 라인 번호"""
    by_line = collections.defaultdict(set); run_lines = collections.defaultdict(set)
    for r in g['runs']:
        a_, b_ = lift(r['a']), lift(r['b'])
        for t in r['texts']:
            for tok in t.split():
                if re.fullmatch(r'\d{5}', tok):
                    by_line[tok] |= {a_, b_}; run_lines[frozenset((a_, b_))].add(tok)
    return by_line, run_lines

def path_lines(a, b, adj, equip, run_lines):
    """a에서 b까지 다른 장비를 지나지 않는 모든 단순 경로 위 선의 라인 번호 집합"""
    out, stack = set(), [(a, [a])]
    while stack:
        v, path = stack.pop()
        for w in adj[v]:
            if w in path:
                continue
            if w == b:
                p = path + [w]
                for x, y in zip(p, p[1:]):
                    out |= run_lines.get(frozenset((x, y)), set())
            elif w not in equip:
                stack.append((w, path + [w]))
    return out

def section(g):
    """미리 계산한 연결 정보 줄. 문맥의 '장비 간 배관 연결' 뒤에 붙임."""
    nodes, adj, deg, equip, lift = build(g)
    tag = equip; names = sorted(equip, key=lambda e: tag[e])
    R = {e: reach_from([e], adj, equip) for e in equip}
    by_line, run_lines = line_numbers(g, lift)
    L = ['## 미리 계산한 연결 정보 (장비에 직접 붙은 연결선 수, 이어진 장비 쌍의 최단 경로 중간 요소 수와 경로 위 라인 번호, 라인 번호에서 도달하는 장비)']
    for e in names:
        L.append(f"{tag[e]} 연결선수={deg[e]}")
    for a, b in itertools.combinations(names, 2):
        if b in R[a]:
            k = shortest_inner(a, b, adj, equip); ls = sorted(path_lines(a, b, adj, equip, run_lines))
            L.append(f"{tag[a]}–{tag[b]} 중간요소수={k} 경로라인={','.join(ls) if ls else '없음'}")
    for ln in sorted(by_line):
        ends = by_line[ln]
        out = {x for x in ends if x in equip} | reach_from([x for x in ends if x not in equip], adj, equip)
        L.append(f"라인 {ln} → {', '.join(sorted(tag[x] for x in out)) if out else '없음'}")
    return L
