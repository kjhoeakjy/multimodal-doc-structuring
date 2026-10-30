"""관계 그래프를 기존 텍스트 LLM에 전달할 문자열로 만든다."""
import sys, json, re, collections

NOTES = {}
def name_of(n):
    # 장비 태그(문자 1 + 숫자 4). 문자 인식이 0을 O로 읽은 경우를 되돌림
    tags = [t[0] + t[1:].replace('O', '0') for t in n['texts'] if re.match(r'^[A-Z][0-9O]{4}$', t)]
    if tags:
        return tags[0]
    if n['role'] == 'instrument':
        return ' '.join(n['texts'][:2])
    # 노즐 번호(N1 등)·치수 숫자는 이름으로 쓰지 않음
    cands = [t for t in n['texts'] if not re.match(r'^N[0-9I]{1,2}$', t) and not re.match(r'^[\d.,/\-%]+$', t)]
    if cands:
        return cands[0]
    if n['id'] in NOTES:
        return NOTES[n['id']]
    return n['id']

NOZ = re.compile(r'^N[0-9I]{1,2}$'); DN = re.compile(r'^\d{2,3}$')
def nozzles_of(n):
    """장비 라벨에서 접속구 번호와 바로 뒤 호칭 지름 쌍을 뽑음(N1 80 → N1:DN80)."""
    out, ts = [], n['texts']
    for i, t in enumerate(ts):
        if NOZ.match(t):
            dn = ts[i + 1] if i + 1 < len(ts) and DN.match(ts[i + 1]) else None
            out.append(t.replace('I', '1') + (f':DN{dn}' if dn else ''))
    return out

LINE_LABEL = re.compile(r'^([A-Z]{2,3}[a-z]?) (\d{5}) (\w+) (\d{2,3})$')
def line_fields(texts):
    """배관 라벨 '유체 라인번호 등급 호칭지름' 형식을 항목으로 풀어 씀."""
    for t in texts:
        m = LINE_LABEL.match(t)
        if m:
            return f" 라인={m.group(2)} 유체={m.group(1)} 등급={m.group(3)} DN={m.group(4)}"
    return ''

def node_line(n, bbox_s=''):
    extra = f" 설명대상={n['annotates']}" if n.get('annotates') else ''
    noz = nozzles_of(n) if n['role'] == 'equipment' else []
    nz = f" 접속구={','.join(noz)}" if noz else ''
    return f"{n['id']} 종류={n['role']} 이름={name_of(n)} 라벨={'|'.join(n['texts']) or '-'}{nz} {bbox_s}{extra}"

def main(graph_path, out_txt, question_node=None, depth=3):
    g = json.load(open(graph_path))
    nodes = {n['id']: n for n in g['nodes']}
    for n in g['nodes']:
        if n['role'] == 'note' and n.get('annotates') and n['texts']:
            NOTES[n['annotates']] = n['texts'][0]
    def label(nid):
        if nid in nodes:
            n = nodes[nid]
            return f"{nid}[{n['role']} {name_of(n)}]"
        return nid
    def bbox(nid):
        if nid in nodes:
            return 'bbox=(' + ','.join(f"{v:.1f}" for v in nodes[nid]['bbox']) + ')'
        j = next((j for j in g['junctions'] if j['id'] == nid), None)
        return f"pt=({j['pt'][0]:.1f},{j['pt'][1]:.1f})" if j else ''
    # 노즐은 소속 장비로 올린다
    def lift(nid):
        n = nodes.get(nid)
        return n['attached_to'] if n and n.get('attached_to') else nid
    lines = []
    lines.append("# 그림 관계 그래프 (좌표 단위 mm, 원점 좌상단)")
    lines.append("## 요소")
    for n in g['nodes']:
        if n['role'] in ('mark', 'arrow') or n.get('attached_to'):
            continue
        lines.append(node_line(n, bbox(n['id'])))
    lines.append("## 분기점")
    for j in g['junctions']:
        lines.append(f"{j['id']} pt=({j['pt'][0]:.1f},{j['pt'][1]:.1f})")
    lines.append("## 연결 (선과 접점으로 확인한 관계)")
    for r in g['runs']:
        a, b = lift(r['a']), lift(r['b'])
        if a == b:
            continue
        arrow = ''
        if r['arrows']:
            d = nodes[r['arrows'][0]]['direction']
            (x0, y0), (x1, y1) = r['coords'][0], r['coords'][-1]
            dot = d[0] * (x1 - x0) + d[1] * (y1 - y0)
            arrow = f" 흐름={'A→B' if dot > 0 else 'B→A'}"
        gap = f" 간격={r['gap']}mm(후보)" if r['gap'] else ''
        txt = (f" 라벨={'|'.join(r['texts'])}" + line_fields(r['texts'])) if r['texts'] else ''
        path = '→'.join(f"({x:.1f},{y:.1f})" for x, y in r['coords'])
        lines.append(f"{r['id']} 종류={r['kind']} A={label(a)} B={label(b)}{arrow}{txt}{gap} 경로={path}")
    lines.append("## 표")
    for i, t in enumerate(g['tables']):
        lines.append(f"t{i} bbox=({','.join(f'{v:.1f}' for v in t['bbox'])}) 행수={len(t['rows'])} 첫행={' / '.join(t['rows'][0])}")
    open(out_txt, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    # 질의용 부분 그래프: 지정 요소에서 배관 연결을 따라 depth 단계
    if question_node:
        start = next((n['id'] for n in g['nodes'] if name_of(n) == question_node), None)
        adj = collections.defaultdict(list)
        for r in g['runs']:
            a, b = lift(r['a']), lift(r['b'])
            if a != b and r['kind'] == 'pipe':
                adj[a].append((b, r)); adj[b].append((a, r))
        seen, frontier, sub = {start}, [start], []
        for _ in range(depth):
            nxt = []
            for v in frontier:
                for w, r in adj[v]:
                    if (v, w, r['id']) in {(x, y, z) for x, y, z in sub} or (w, v, r['id']) in {(x, y, z) for x, y, z in sub}:
                        continue
                    sub.append((v, w, r['id']))
                    if w not in seen:
                        seen.add(w); nxt.append(w)
            frontier = nxt
        out = [f"# 질의 부분 그래프: {question_node} 기준 {depth}단계"]
        for v, w, rid in sub:
            r = next(x for x in g['runs'] if x['id'] == rid)
            arrow = ''
            if r['arrows']:
                d = nodes[r['arrows'][0]]['direction']
                (x0, y0), (x1, y1) = r['coords'][0], r['coords'][-1]
                dot = d[0] * (x1 - x0) + d[1] * (y1 - y0)
                src = lift(r['a']) if dot > 0 else lift(r['b'])
                arrow = f" 흐름={label(src)}→{label(lift(r['b']) if dot > 0 else lift(r['a']))}"
            out.append(f"{label(v)} --{rid}{'(' + '|'.join(r['texts']) + ')' if r['texts'] else ''}--> {label(w)}{arrow} 근거={bbox(v)} {bbox(w)}")
        open(out_txt.replace('.txt', f'_{question_node}.txt'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
        print('\n'.join(out))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
