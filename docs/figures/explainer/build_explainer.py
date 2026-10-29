#!/usr/bin/env python3
"""도면 한 장(DEXPI C01)이 인식되고 그래프로 바뀌어 색인되는 과정을 단계별 모션으로 보이는 HTML 생성.
입력: 자체 변환 SVG(선·곡선·타원·문자), 추출 결과 graph.json·graph.txt. 실행: python3 build_explainer.py"""
import json, re, math, random, html, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
svg_src = open(f'{ROOT}/examples/public-documents/pid/input/C01.svg', encoding='utf-8').read()
G = json.load(open(f'{ROOT}/examples/dexpi-reference-pid/output/graph.json', encoding='utf-8'))
gtxt = open(f'{ROOT}/examples/dexpi-reference-pid/output/graph.txt', encoding='utf-8').read().splitlines()
sub = open(f'{ROOT}/examples/dexpi-reference-pid/output/graph_P4712.txt', encoding='utf-8').read().splitlines()

# ---- 1. 원본 SVG 요소에 종류 표시 ----
body = []
counts = dict(line=0, curve=0, arc=0, text=0)
for ln in svg_src.splitlines():
    s = ln.strip()
    if s.startswith('<path'):
        kind = 'curve' if re.search(r'\sA\s', s) or ' A ' in s else 'line'
        counts[kind] += 1
        m = re.search(r'd="M ([\d.\-]+) ([\d.\-]+)', s)
        x = float(m.group(1)) if m else 0
        s = s.replace('<path', f'<path class="p p-{kind}" data-x="{x:.0f}"', 1)
    elif s.startswith('<ellipse'):
        counts['arc'] += 1
        m = re.search(r'cx="([\d.\-]+)"', s); x = float(m.group(1)) if m else 0
        s = s.replace('<ellipse', f'<ellipse class="p p-arc" data-x="{x:.0f}"', 1)
    elif s.startswith('<text'):
        counts['text'] += 1
        m = re.search(r'translate\(([\d.\-]+) ', s); x = float(m.group(1)) if m else 0
        s = s.replace('<text', f'<text class="p p-text" data-x="{x:.0f}"', 1)
        s = s.replace('font-family="Calibri"', 'font-family="IBM Plex Sans, Noto Sans KR, sans-serif"')
    elif s.startswith('<rect') or s.startswith('<svg') or s.startswith('</svg') or s.startswith('<?xml'):
        continue
    body.append(s)
drawing = '\n'.join(body)

# ---- 2. 추출 결과 ----
nodes = G['nodes']; runs = G['runs']; juncs = G['junctions']; labels = G['labels']; tables = G['tables']
nid = {n['id']: n for n in nodes}
jid = {j['id']: j for j in juncs}

def center(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
def pos(v):
    if v in nid: return center(nid[v]['bbox'])
    if v in jid: return tuple(jid[v]['pt'])
    return None

# 그래프 배치(힘 기반): 그림 좌표에서 출발해 풀어 놓음
gnodes = [n['id'] for n in nodes if n['role'] in ('equipment', 'instrument', 'symbol', 'nozzle', 'note') and (n['degree'] > 0 or n['role'] in ('equipment', 'instrument'))]
gnodes += [j['id'] for j in juncs]
gset = set(gnodes)
edges = [(r['a'], r['b'], r) for r in runs if r['a'] in gset and r['b'] in gset]
random.seed(3)
P = {v: list(pos(v)) for v in gnodes}
k = 14.0
for it in range(260):
    temp = 6.0 * (1 - it / 260) + 0.3
    disp = {v: [0.0, 0.0] for v in gnodes}
    for i, a in enumerate(gnodes):
        for b in gnodes[i + 1:]:
            dx = P[a][0] - P[b][0]; dy = P[a][1] - P[b][1]
            d = math.hypot(dx, dy) + 1e-3
            f = k * k / d
            disp[a][0] += dx / d * f; disp[a][1] += dy / d * f
            disp[b][0] -= dx / d * f; disp[b][1] -= dy / d * f
    for a, b, _ in edges:
        dx = P[a][0] - P[b][0]; dy = P[a][1] - P[b][1]
        d = math.hypot(dx, dy) + 1e-3
        f = d * d / k
        disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f
        disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
    for v in gnodes:
        dx, dy = disp[v]; d = math.hypot(dx, dy) + 1e-3
        P[v][0] += dx / d * min(d, temp); P[v][1] += dy / d * min(d, temp)
xs = [p[0] for p in P.values()]; ys = [p[1] for p in P.values()]
x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
layout = {v: [round((p[0] - x0) / (x1 - x0) * 560 + 20, 1), round((p[1] - y0) / (y1 - y0) * 360 + 20, 1)] for v, p in P.items()}
start = {v: pos(v) for v in gnodes}

def role_of(v):
    return nid[v]['role'] if v in nid else 'junction'
def name_of(v):
    if v in nid:
        t = nid[v]['texts']
        return t[0] if t else nid[v]['role']
    return v

data = dict(
    counts=counts,
    nodes=[dict(id=n['id'], role=n['role'], bbox=n['bbox'], texts=n['texts'][:3], degree=n['degree']) for n in nodes],
    runs=[dict(id=r['id'], a=r['a'], b=r['b'], coords=r['coords'], kind=r['kind'], dashed=r['dashed'], gap=r['gap'], texts=r['texts']) for r in runs],
    junctions=juncs,
    labels=[dict(text=l['text'], bbox=l['bbox'], owner=l['owner']) for l in labels],
    tables=[dict(bbox=t['bbox'], rows=len(t['rows']), first=t['rows'][0]) for t in tables],
    graph=dict(nodes=[dict(id=v, role=role_of(v), name=name_of(v), start=start[v], end=layout[v]) for v in gnodes],
               edges=[dict(id=r['id'], a=a, b=b, kind=r['kind'], label=(r['texts'][0] if r['texts'] else '')) for a, b, r in edges]),
    serial=[l for l in gtxt if l.strip()][:40],
    subgraph=sub,
    table_rows=[[r for r in t['rows']] for t in tables][0][:4],
)

here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, 'template.html'), encoding='utf-8').read()
out = tpl.replace('/*__DATA__*/', 'const D = ' + json.dumps(data, ensure_ascii=False) + ';').replace('<!--__DRAWING__-->', drawing)
open(os.path.join(here, '도면-구조화-과정.html'), 'w', encoding='utf-8').write(out)
print(counts, len(nodes), len(runs), len(gnodes), len(edges), len(out))
