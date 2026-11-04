"""PID2Graph의 graphml(기호·선 교차·꺾임 노드와 간선)을 llm-qa 그래프 형식(graph.json)으로 바꾸고 합성 문자(장비 태그·접속구·계기 번호·라인 라벨)를 붙인다.
PID2Graph에는 문자 속성이 없으므로 위상만 쓰고 문자는 DEXPI 예시 도면(C01)의 형식을 따라 만든다. 학습용 그래프를 만들기 위한 것이며 정답 대조에는 쓰지 않는다.
노드 종류 대응: tank·pump·general → equipment, instrumentation → instrument, valve·inlet/outlet → symbol, crossing·connector·arrow·junction·bend·corner·ankle → 분기점, background → 제외.
사용: python synth_graph.py <graphml 또는 폴더> <출력 폴더> [--seed 0] [--limit N]
결과: <출력 폴더>/<이름>/graph.json (make_train.py 입력)"""
import os, sys, json, random, argparse, collections, xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'pid2graph'))
from gt_from_graphml import load, bbox_of, label_of, edge_kind, PASS_WORDS, SKIP_WORDS

PREFIX = {'tank': ['T', 'V', 'D'], 'pump': ['P', 'K'], 'general': ['H', 'E', 'F', 'M']}
FUNCS = ['PI', 'TI', 'FI', 'LI', 'PT', 'TT', 'FT', 'LT', 'PIC', 'TIC', 'FIC', 'LIC', 'PICSA', 'TICSA', 'LICA', 'HS', 'PSV', 'FQI']
FLUIDS = ['MNb', 'PWa', 'CWS', 'CWR', 'STa', 'NGa', 'AIR', 'OIL']
CLASSES = ['75HB13', '66KL21', '73KH12', '75SA21', '80HC10']
DNS = ['25', '50', '80', '100', '150', '200']

def role_of(lab):
    l = lab.lower()
    if any(w in l for w in SKIP_WORDS):
        return None
    if any(w in l for w in PASS_WORDS):
        return 'junction'
    if 'tank' in l or 'pump' in l or 'general' in l:
        return 'equipment'
    if 'instrument' in l:
        return 'instrument'
    return 'symbol'     # valve, inlet/outlet 등

def convert(path, rnd):
    nodes, edges = load(path)
    out, junctions, idmap = [], [], {}
    cls = {}
    for nid, d in nodes.items():
        bb, lab = bbox_of(d), label_of(d)
        role = role_of(lab)
        if role is None or bb is None:
            continue
        cls[nid] = lab.lower()
        if role == 'junction':
            jid = f"j{len(junctions)}"; junctions.append(dict(id=jid, pt=[(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2])); idmap[nid] = jid
        else:
            n = dict(id=f"n{len(out)}", role=role, texts=[], bbox=bb, primitives=1, degree=0, attached_to=None, direction=None, annotates=None)
            out.append(n); idmap[nid] = n['id']
    if not out:
        return None
    scale = 420.0 / max(max(n['bbox'][2] for n in out), 1.0)     # 픽셀 → mm(가로 420 mm 기준)
    for n in out:
        n['bbox'] = [round(v * scale, 2) for v in n['bbox']]
    for j in junctions:
        j['pt'] = [round(v * scale, 2) for v in j['pt']]
    pos = {n['id']: ((n['bbox'][0] + n['bbox'][2]) / 2, (n['bbox'][1] + n['bbox'][3]) / 2) for n in out}
    pos.update({j['id']: tuple(j['pt']) for j in junctions})
    runs, seen = [], set()
    for a, b, d in edges:
        if a not in idmap or b not in idmap or idmap[a] == idmap[b]:
            continue
        key = frozenset((idmap[a], idmap[b]))
        if key in seen:
            continue
        seen.add(key)
        runs.append(dict(id=f"r{len(runs)}", a=idmap[a], b=idmap[b], coords=[list(pos[idmap[a]]), list(pos[idmap[b]])], width=0.5, dashed=False,
                         kind=edge_kind(d), gap=0, arrows=[], texts=[]))
    deg = collections.Counter()
    for r in runs:
        deg[r['a']] += 1; deg[r['b']] += 1
    for n in out:
        n['degree'] = deg[n['id']]
    # 합성 문자: 장비 태그와 접속구, 계기 기능·번호, 밸브 번호, 라인 라벨
    used = set(); base = rnd.randrange(10, 90) * 100
    def fresh4():
        while True:
            v = rnd.randrange(1000, 9999)
            if v not in used:
                used.add(v); return v
    equip = [n for n in out if n['role'] == 'equipment']
    for n in equip:
        src = next(k for k, v in idmap.items() if v == n['id']); kind = cls[src]
        pre = rnd.choice(PREFIX['tank'] if 'tank' in kind else PREFIX['pump'] if 'pump' in kind else PREFIX['general'])
        n['texts'] = [f"{pre}{fresh4()}"]
        for i in range(max(1, n['degree'])):
            n['texts'] += [f"N{i + 1}", rnd.choice(DNS)]
    for n in (n for n in out if n['role'] == 'instrument'):
        n['texts'] = [rnd.choice(FUNCS), f"{base + rnd.randrange(0, 99)}.{rnd.randrange(1, 9):02d}"]
    for n in (n for n in out if n['role'] == 'symbol'):
        if rnd.random() < 0.5:
            n['texts'] = [f"{rnd.choice(CLASSES)}-{rnd.choice(DNS)}"]
    eq = {n['id'] for n in equip}; ln = rnd.randrange(10000, 89999)
    for r in runs:
        if r['kind'] != 'pipe':
            continue
        if r['a'] in eq or r['b'] in eq or rnd.random() < 0.15:
            ln += rnd.randrange(1, 4)
            r['texts'] = [f"{rnd.choice(FLUIDS)} {ln} {rnd.choice(CLASSES)} {rnd.choice(DNS)}"]
    page = [420.0, round(max(n['bbox'][3] for n in out), 1)]
    return dict(page=page, nodes=out, junctions=junctions, runs=runs, labels=[], tables=[],
                counts=dict(primitives=0, texts=sum(len(n['texts']) for n in out), nodes=len(out), runs=len(runs), junctions=len(junctions), tables=0, dropped_fragments=0))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('out'); ap.add_argument('--seed', type=int, default=0); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    files = [a.src] if os.path.isfile(a.src) else sorted(os.path.join(d, f) for d, _, fs in os.walk(a.src) for f in fs if f.lower().endswith('.graphml'))
    if a.limit:
        files = files[:a.limit]
    n_ok = 0
    for i, f in enumerate(files):
        g = convert(f, random.Random(a.seed * 100003 + i))
        if not g or not any(n['role'] == 'equipment' for n in g['nodes']):
            continue
        name = os.path.splitext(os.path.basename(f))[0]
        os.makedirs(os.path.join(a.out, name), exist_ok=True)
        json.dump(g, open(os.path.join(a.out, name, 'graph.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        n_ok += 1
    print(f'{len(files)}개 중 {n_ok}개 변환 → {a.out}')

if __name__ == '__main__':
    main()
