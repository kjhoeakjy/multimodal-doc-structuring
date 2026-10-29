"""추출한 관계 그래프를 원본 DEXPI XML의 연결 정보와 대조한다."""
import sys, json, math, collections, xml.etree.ElementTree as ET
from shapely.geometry import box, Point, LineString

def load_gt(xml_path, page_h):
    root = ET.parse(xml_path).getroot()
    comps, conns, labels = {}, [], []
    def loc(el):
        p = el.find('Position/Location')
        return (float(p.get('X')), page_h - float(p.get('Y'))) if p is not None else None
    def nodes(el):
        cp = el.find('ConnectionPoints')
        return [loc(n) for n in (cp.findall('Node') if cp is not None else []) if loc(n)]
    KINDS = ('Equipment', 'Nozzle', 'PipingComponent', 'PipeOffPageConnector', 'ProcessInstrumentationFunction',
             'ActuatingSystem', 'PipingNetworkSegment', 'PipingNetworkSystem')
    def walk(el, parent, seg):
        cid, tag = el.get('ID'), el.tag
        if tag in KINDS and cid:
            ga = {g.get('Name'): g.get('Value') for g in el.findall('GenericAttributes/GenericAttribute')}
            comps[cid] = dict(kind=tag, cls=el.get('ComponentClass'), tag=ga.get('TagNameAssignmentClass'),
                              parent=parent, pos=loc(el), nodes=nodes(el), seg=seg, children=[])
            if parent in comps:
                comps[parent]['children'].append(cid)
            parent = cid
        if tag == 'Connection' and seg:
            conns.append(dict(seg=seg, frm=el.get('FromID'), to=el.get('ToID')))
        if tag == 'Text' and el.get('String'):
            labels.append(dict(text=el.get('String'), pos=loc(el), owner=parent))
        if tag == 'CenterLine' and seg:
            comps[seg].setdefault('lines', []).append([(float(c.get('X')), page_h - float(c.get('Y'))) for c in el.findall('Coordinate')])
        for ch in el:
            walk(ch, parent, cid if tag == 'PipingNetworkSegment' else seg)
    walk(root, None, None)
    return comps, conns, labels

def entity(comps, cid):
    """노즐은 소속 장비로, 그 밖의 구성 요소는 자기 자신으로 본다."""
    c = comps.get(cid)
    if c is None:
        return None
    if c['kind'] == 'Nozzle' and c['parent'] in comps:
        return c['parent']
    return cid

def gt_adjacency(comps, conns):
    """배관 구간마다 시작 요소, 구간 안의 배관 부품, 끝 요소의 순서로 인접 쌍을 만든다."""
    pairs = set()
    by_seg = collections.defaultdict(list)
    for c in conns:
        by_seg[c['seg']].append(c)
    for seg, cs in by_seg.items():
        inline = [k for k in comps[seg]['children'] if comps[k]['kind'] == 'PipingComponent'
                  and comps[k]['cls'] not in ('PipeFlowArrow',)]
        for c in cs:
            chain = [c['frm']] + [k for k in inline if k not in (c['frm'], c['to'])] + [c['to']]
            chain = [entity(comps, k) for k in chain]
            chain = [k for i, k in enumerate(chain) if k and (i == 0 or k != chain[i - 1])]
            for a, b in zip(chain, chain[1:]):
                pairs.add(tuple(sorted((a, b))))
    return pairs

def main(graph_path, xml_path, out_md):
    g = json.load(open(graph_path))
    comps, conns, gt_labels = load_gt(xml_path, g['page'][1])
    nodes = {n['id']: n for n in g['nodes']}
    juncs = {j['id']: j for j in g['junctions']}
    # 추출 노드로 대응: 노즐은 붙어 있는 장비로 올린다
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
        pts = ([c['pos']] if c['pos'] else []) + c['nodes']
        hits = [match_point(p) for p in pts]
        hits = [h for h in hits if h]
        if hits:
            gt2ex[cid] = lift(collections.Counter(hits).most_common(1)[0][0])
    # 추출 인접 쌍: 배관 구간의 양 끝. 열린 끝은 제외
    ex_pairs, pair_kind = set(), {}
    for r in g['runs']:
        a, b = r['a'], r['b']
        if a.startswith('open') or b.startswith('open'):
            continue
        a, b = lift(a), lift(b)
        if a != b:
            key = tuple(sorted((a, b)))
            ex_pairs.add(key)
            roles = {nodes[x]['role'] for x in (a, b) if x in nodes}
            pair_kind[key] = 'signal' if (r['kind'] == 'signal' or roles & {'instrument'}) else 'pipe'
    gt_pairs = gt_adjacency(comps, conns)
    rows, hit = [], 0
    for a, b in sorted(gt_pairs):
        ea, eb = gt2ex.get(a), gt2ex.get(b)
        ok = ea is not None and eb is not None and tuple(sorted((ea, eb))) in ex_pairs
        hit += ok
        rows.append((a, b, ea, eb, ok))
    # 추출 쌍 중 정답에 없는 것
    ex2gt = collections.defaultdict(set)
    for k, v in gt2ex.items():
        ex2gt[v].add(k)
    extra = []
    for a, b in sorted(ex_pairs):
        cand = {tuple(sorted((x, y))) for x in ex2gt.get(a, set()) for y in ex2gt.get(b, set())}
        if not (cand & gt_pairs):
            extra.append((a, b, sorted(ex2gt.get(a, [])), sorted(ex2gt.get(b, [])), pair_kind[(a, b)]))
    # 라벨 소속 비교 (장비 태그, 밸브 태그, 계기 태그, 노즐 라벨)
    ex_label_owner = {}
    for l in g['labels']:
        if l['owner']:
            ex_label_owner[(l['text'], round(l['x']), round(l['y']))] = (l['owner'][0], l['owner'][1])
    lab_rows, lab_hit, lab_n = [], 0, 0
    for l in gt_labels:
        own = l['owner']
        if own not in comps or comps[own]['kind'] in ('PipingNetworkSegment', 'PipingNetworkSystem', 'ActuatingSystem'):
            continue
        # 추출 라벨 중 같은 문자열이고 위치가 가장 가까운 것
        best = None
        for el in g['labels']:
            if el['text'] == l['text']:
                d = math.dist((el['x'], el['y']), l['pos'])
                if best is None or d < best[0]:
                    best = (d, el)
        if best is None or best[0] > 8:
            continue
        el = best[1]
        lab_n += 1
        want = gt2ex.get(entity(comps, own))
        got = None
        if el['owner'] and el['owner'][0] == 'node':
            got = lift(f"n{el['owner'][1]}")
        ok = want is not None and got == want
        lab_hit += ok
        lab_rows.append((l['text'], comps[own]['cls'], want, got, ok))
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write("# 정답 대조 결과\n\n")
        f.write(f"정답 인접 쌍 {len(gt_pairs)}개 중 {hit}개 복원 (재현율 {hit/len(gt_pairs):.2f}). ")
        n_sig = sum(1 for e in extra if e[4] == 'signal')
        f.write(f"추출 인접 쌍 {len(ex_pairs)}개 중 정답에 없는 쌍 {len(extra)}개. 이 중 {n_sig}개는 계측 신호선 연결로 배관 정답의 범위 밖이고 {len(extra)-n_sig}개는 오류임. 배관 쌍 기준 정밀도 {(len(ex_pairs)-len(extra))/max(1,len(ex_pairs)-n_sig):.2f}.\n\n")
        f.write(f"요소 라벨 {lab_n}개 중 소속이 맞는 라벨 {lab_hit}개 ({lab_hit/max(1,lab_n):.2f}).\n\n")
        f.write("## 정답 인접 쌍\n\n| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |\n|---|---|---|---|---|\n")
        for a, b, ea, eb, ok in rows:
            f.write(f"| {a} | {b} | {ea} | {eb} | {'O' if ok else 'X'} |\n")
        f.write("\n## 정답에 없는 추출 쌍\n\n| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |\n|---|---|---|---|---|\n")
        for a, b, ga, gb, kind in extra:
            f.write(f"| {a} | {b} | {', '.join(ga) or '-'} | {', '.join(gb) or '-'} | {'계측 신호선' if kind == 'signal' else '오류'} |\n")
        f.write("\n## 라벨 소속\n\n| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |\n|---|---|---|---|---|\n")
        for t, cls, want, got, ok in lab_rows:
            f.write(f"| {t} | {cls} | {want} | {got} | {'O' if ok else 'X'} |\n")
    print(f"pairs {hit}/{len(gt_pairs)} extra {len(extra)}/{len(ex_pairs)} labels {lab_hit}/{lab_n}")
    json.dump(dict(gt2ex=gt2ex), open(out_md.replace('.md', '.json'), 'w'), indent=1)

if __name__ == '__main__':
    main(*sys.argv[1:4])
