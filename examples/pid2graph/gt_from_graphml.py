"""PID2Graph의 graphml 정답을 기호 간 인접 쌍으로 바꾼다.

노드는 기호(7종)와 선의 교차·꺾임·경계 노드로 나뉜다. 기호가 아닌 노드는 통과시켜
기호와 기호가 선으로 이어진 쌍을 만든다. 간선 종류가 모두 실선이면 배관, 하나라도
점선이면 신호선으로 본다. 결과는 truth.json(기호 목록·인접 쌍, 픽셀 좌표).
"""
import sys, json, collections, xml.etree.ElementTree as ET

NS = '{http://graphml.graphdrawing.org/xmlns}'
PASS_WORDS = ('cross', 'ankle', 'border', 'junction', 'connector', 'corner', 'bend')

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def load(path):
    root = ET.parse(path).getroot()
    keys = {k.get('id'): (k.get('attr.name') or k.get('id')) for k in root.iter(NS + 'key')}
    def data(el):
        return {keys.get(d.get('key'), d.get('key')): (d.text or '').strip() for d in el.findall(NS + 'data')}
    nodes, edges = {}, []
    for n in root.iter(NS + 'node'):
        nodes[n.get('id')] = data(n)
    for e in root.iter(NS + 'edge'):
        edges.append((e.get('source'), e.get('target'), data(e)))
    return nodes, edges

def pick(d, names):
    low = {k.lower().replace('_', '').replace('-', ''): v for k, v in d.items()}
    for n in names:
        if n in low and low[n] != '':
            return low[n]
    return None

def bbox_of(d):
    vals = [pick(d, (a,)) for a in ('xmin', 'ymin', 'xmax', 'ymax')]
    if all(v is not None for v in vals):
        return [_num(v) for v in vals]
    b = pick(d, ('bbox', 'box', 'boundingbox'))
    if b:
        parts = [p for p in b.replace('[', ' ').replace(']', ' ').replace(',', ' ').split() if p]
        if len(parts) == 4:
            return [float(p) for p in parts]
    x, y, w, h = (pick(d, (a,)) for a in ('x', 'y', 'width', 'height'))
    if None not in (x, y, w, h):
        x, y, w, h = map(float, (x, y, w, h))
        return [x, y, x + w, y + h]
    return None

def label_of(d):
    v = pick(d, ('label', 'class', 'classname', 'type', 'category', 'name', 'symbol'))
    return (v or '').strip()

def is_symbol(lab, bb):
    l = lab.lower()
    if any(w in l for w in PASS_WORDS):
        return False
    return bb is not None

def edge_kind(d):
    v = (label_of(d) or pick(d, ('linetype', 'style', 'kind')) or '').lower()
    return 'signal' if ('non' in v or 'dash' in v or 'signal' in v) else 'pipe'

def convert(path, out_json):
    nodes, edges = load(path)
    syms, passn = {}, set()
    for nid, d in nodes.items():
        bb, lab = bbox_of(d), label_of(d)
        if is_symbol(lab, bb):
            syms[nid] = dict(id=nid, cls=lab, bbox=bb)
        else:
            passn.add(nid)
    adj = collections.defaultdict(list)
    for a, b, d in edges:
        k = edge_kind(d)
        adj[a].append((b, k)); adj[b].append((a, k))
    pairs = {}
    for s in syms:
        # 통과 노드를 지나 처음 만나는 기호까지. 같은 경로에 점선이 하나라도 있으면 신호선
        stack = [(s, 'pipe', frozenset([s]))]
        while stack:
            cur, kind, seen = stack.pop()
            for nxt, k in adj.get(cur, []):
                if nxt in seen:
                    continue
                kk = 'signal' if 'signal' in (kind, k) else 'pipe'
                if nxt in syms:
                    if nxt != s:
                        key = tuple(sorted((s, nxt)))
                        pairs[key] = 'signal' if pairs.get(key) == 'signal' or kk == 'signal' else 'pipe'
                elif nxt in passn:
                    stack.append((nxt, kk, seen | {nxt}))
    out = dict(source=path, symbols=list(syms.values()), pass_nodes=len(passn),
               pairs=[dict(a=a, b=b, kind=k) for (a, b), k in sorted(pairs.items())],
               classes=dict(collections.Counter(v['cls'] for v in syms.values())))
    json.dump(out, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n_pipe = sum(1 for p in pairs.values() if p == 'pipe')
    print(f"symbols {len(syms)} pass {len(passn)} pairs {len(pairs)} (pipe {n_pipe}, signal {len(pairs)-n_pipe})")
    return out

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
