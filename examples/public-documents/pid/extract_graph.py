"""벡터 도식(SVG)의 그리기 요소에서 관계 그래프를 만든다.

입력으로 선, 곡선, 타원, 문자와 선 굵기, 점선 여부만 사용한다.
그룹 이름, 식별자, 기호 정의 이름, 색상 같은 정보는 읽지 않는다.
"""
import sys, json, math, re, collections
from svgelements import (SVG, Path, Line, Shape, Text, Ellipse, Circle, Arc,
                         CubicBezier, QuadraticBezier, Point)
from shapely.geometry import LineString, Point as SPoint, box
from shapely.ops import unary_union

LONG = 6.0          # 이 길이(mm) 이상인 축 평행 직선을 선 후보로 봄
SIGNAL_RATIO = 0.5   # 가장 굵은 선 부류 대비 이 비율보다 가는 선은 신호선
TOUCH = 0.6         # 접점 판정 거리(mm)
NEAR_NODE = 4.0     # 문자와 요소의 연결 판정 거리(mm)
NEAR_RUN = 6.0      # 문자와 선의 연결 판정 거리(mm)
GAP = 5.0           # 열린 끝을 연장해 연결 후보를 찾는 최대 거리(mm). 도면의 주 배관 굵기에 비례해 조정함

# ---------- 1. 기본 요소 읽기 ----------
def load_primitives(path):
    svg = SVG.parse(path, reify=True)
    W, H = float(svg.width), float(svg.height)
    prims, texts = [], []
    def style(e):
        return dict(width=round(float(e.stroke_width or 0), 2),
                    dashed=bool(e.values.get('stroke-dasharray') not in (None, 'none')))
    for e in svg.elements():
        if isinstance(e, Text):
            if not e.text or not e.text.strip():
                continue
            p = e.transform.point_in_matrix_space(Point(e.x, e.y))
            ang = round(math.degrees(math.atan2(e.transform.b, e.transform.a))) % 180
            size = float(e.font_size or 3)
            texts.append(dict(text=e.text.strip(), x=p.x, y=p.y, angle=ang, size=size,
                              anchor=e.anchor or 'start', width=0.5 * size * len(e.text.strip())))
        elif isinstance(e, (Ellipse, Circle)):
            cx, cy, rx, ry = float(e.cx), float(e.cy), float(e.rx), float(e.ry)
            pts = [(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in [i * math.pi / 18 for i in range(37)]]
            prims.append(dict(kind='ellipse', geom=LineString(pts), length=2 * math.pi * max(rx, ry),
                              ends=[], axis=False, **style(e)))
        elif isinstance(e, Shape):
            p = e if isinstance(e, Path) else Path(e)
            p.reify()
            for s in p:
                if isinstance(s, Line):
                    a, b = (s.start.x, s.start.y), (s.end.x, s.end.y)
                    L = math.dist(a, b)
                    if L < 1e-6:
                        continue
                    axis = abs(a[0] - b[0]) < 1e-3 or abs(a[1] - b[1]) < 1e-3
                    prims.append(dict(kind='line', geom=LineString([a, b]), length=L, ends=[a, b], axis=axis, **style(e)))
                elif isinstance(s, (Arc, CubicBezier, QuadraticBezier)):
                    pts = [(q.x, q.y) for q in (s.point(i / 12) for i in range(13))]
                    prims.append(dict(kind='curve', geom=LineString(pts), length=math.dist(pts[0], pts[-1]),
                                      ends=[pts[0], pts[-1]], axis=False, **style(e)))
    for i, p in enumerate(prims):
        p['id'] = i
    return W, H, prims, texts

def text_bbox(t):
    h, w = t['size'], t['width']
    if t['angle'] in (90, 270):
        half = w / 2 if t['anchor'] == 'middle' else 0
        return box(t['x'] - h, t['y'] - (w if t['anchor'] != 'middle' else half), t['x'] + 0.2 * h,
                   t['y'] + (0 if t['anchor'] != 'middle' else half))
    x0 = t['x'] - (w / 2 if t['anchor'] == 'middle' else (w if t['anchor'] == 'end' else 0))
    return box(x0, t['y'] - h, x0 + w, t['y'] + 0.2 * h)

# ---------- 2. 닫힌 도형 판정 ----------
def closed_components(items):
    """끝점이 서로 맞닿는 요소를 묶고, 모든 끝점이 짝을 이루면 닫힌 도형으로 본다."""
    n = len(items)
    parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    deg = [[0, 0] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            for ai, a in enumerate(items[i]['ends']):
                for bi, b in enumerate(items[j]['ends']):
                    if math.dist(a, b) < TOUCH:
                        parent[find(i)] = find(j); deg[i][ai] += 1; deg[j][bi] += 1
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return [dict(members=g, closed=(len(g) >= 3 and all(deg[i][0] > 0 and deg[i][1] > 0 for i in g)))
            for g in groups.values()]

# ---------- 3. 테두리, 표, 표제란 제거 ----------
def touch_components(items, tol=TOUCH):
    """기하학적으로 맞닿는 요소끼리 묶는다(끝점 일치와 T자 접촉 모두 포함)."""
    n = len(items)
    parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    bounds = [it['geom'].bounds for it in items]
    for i in range(n):
        bi = bounds[i]
        for j in range(i + 1, n):
            bj = bounds[j]
            if bj[0] > bi[2] + tol or bj[2] < bi[0] - tol or bj[1] > bi[3] + tol or bj[3] < bi[1] - tol:
                continue
            if items[i]['geom'].distance(items[j]['geom']) < tol:
                parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())

def boundary_coverage(bb, geoms, extra=None):
    """사각형 경계 네 변이 선으로 덮인 비율."""
    ring = LineString(list(bb.exterior.coords))
    gs = list(geoms) + ([extra] if extra is not None else [])
    covered = unary_union(gs).buffer(TOUCH).intersection(ring).length
    return covered / ring.length

def remove_frame_and_tables(W, H, prims, texts):
    longs = [p for p in prims if p['kind'] == 'line' and p['axis'] and p['length'] >= LONG]
    frame_box = None
    for g in touch_components(longs):
        b = box(*unary_union([longs[i]['geom'] for i in g]).bounds)
        if b.area > 0.8 * W * H and boundary_coverage(b, [longs[i]['geom'] for i in g]) > 0.9:
            if frame_box is None or b.area < frame_box.area:
                frame_box = b
    frame_box = frame_box or box(0, 0, W, H)
    frame_ring = LineString(list(frame_box.exterior.coords))
    inner = frame_box.buffer(-TOUCH)
    prims = [p for p in prims if p['geom'].within(inner)]
    texts = [t for t in texts if text_bbox(t).centroid.within(inner)]
    # 표와 표제란: 서로 맞닿는 선들의 묶음이 사각형 경계를 거의 다 덮고 그 안에 문자가 6개 이상
    longs = [p for p in prims if p['kind'] == 'line' and p['axis'] and p['length'] >= LONG]
    tables, tgeoms = [], []
    for g in touch_components(longs):
        geoms = [longs[i]['geom'] for i in g]
        bb = box(*unary_union(geoms).bounds)
        if len(g) < 3 or bb.area > 0.3 * W * H or boundary_coverage(bb, geoms, frame_ring) < 0.9:
            continue
        inside = [t for t in texts if text_bbox(t).centroid.within(bb.buffer(0.3))]
        if len(inside) < 6:
            continue
        # 밖에서 선이 둘 이상 닿아 있으면 표가 아니라 장비(탑·열교환기 등 격자 모양 기호)
        gids = {id(longs[i]) for i in g}
        attached = sum(1 for p in prims if p['kind'] == 'line' and id(p) not in gids and not p['geom'].within(bb.buffer(0.3))
                       and any(bb.exterior.distance(SPoint(e)) < 2 * TOUCH for e in p['ends']))
        if attached >= 2:
            continue
        rows = collections.defaultdict(list)
        for t in inside:
            rows[round(t['y'], 1)].append(t)
        tables.append(dict(bbox=[round(v, 2) for v in bb.bounds],
                           rows=[[t['text'] for t in sorted(r, key=lambda t: t['x'])] for _, r in sorted(rows.items())]))
        tgeoms.append(bb.buffer(0.3))
    prims = [p for p in prims if not any(p['geom'].within(g) for g in tgeoms)]
    texts = [t for t in texts if not any(text_bbox(t).centroid.within(g) for g in tgeoms)]
    return prims, texts, tables

# ---------- 4. 도형, 기호 묶음, 선 후보 ----------
def cluster(prims, tol):
    n = len(prims)
    parent = list(range(n))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    bounds = [p['geom'].bounds for p in prims]
    for i in range(n):
        bi = bounds[i]
        for j in range(i + 1, n):
            bj = bounds[j]
            if bj[0] > bi[2] + tol or bj[2] < bi[0] - tol or bj[1] > bi[3] + tol or bj[3] < bi[1] - tol:
                continue
            if prims[i]['geom'].distance(prims[j]['geom']) < tol:
                parent[find(i)] = find(j)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(prims[i])
    return list(groups.values())

def build_nodes(prims):
    strokes = [p for p in prims if p['kind'] in ('line', 'curve')]
    shapes, used = [], set()
    for c in closed_components(strokes):            # 끝점이 모두 맞물린 닫힌 도형
        if c['closed']:
            members = [strokes[i] for i in c['members']]
            shapes.append(dict(role='shape', prims=members)); used.update(m['id'] for m in members)
    for p in prims:
        if p['kind'] == 'ellipse' and p['length'] >= 2 * LONG:
            shapes.append(dict(role='shape', prims=[p])); used.add(p['id'])
    from shapely.ops import polygonize
    for s in shapes:
        s['geom'] = unary_union([m['geom'] for m in s['prims']]); s['box'] = box(*s['geom'].bounds)
        polys = list(polygonize(s['geom']))          # 도형의 윤곽 안쪽(상자가 아니라 실제 윤곽)
        s['inner'] = unary_union(polys).buffer(0.2) if polys else s['box'].buffer(0.2)
    def host_of(geom):
        return next((s for s in shapes if geom.within(s['inner'])), None)
    long_lines, short_axis, shorts = [], [], []
    for p in prims:
        if p['id'] in used:
            continue
        h = host_of(p['geom'])
        if h is not None:                      # 도형 내부 요소는 도형의 장식
            h['prims'].append(p); continue
        if p['kind'] == 'line' and p['axis']:
            (long_lines if p['length'] >= LONG else short_axis).append(p)
        else:                                  # 사선, 곡선, 작은 타원은 기호 재료
            shorts.append(p)
    symbols = []
    for g in cluster(shorts, TOUCH):
        geom = unary_union([p['geom'] for p in g])
        role = 'mark' if len(g) == 1 and g[0]['kind'] != 'ellipse' else 'symbol'
        symbols.append(dict(role=role, prims=g, geom=geom))
    # 짧은 축 평행 직선: 긴 선과 같은 축에서 이어지면 선, 기호에 닿으면 기호의 일부, 그 밖에는 짧은 선 조각
    def collinear_with_long(p):
        (x0, y0), (x1, y1) = p['ends']
        horiz = abs(y0 - y1) < 1e-3
        for q in long_lines:
            (a0, b0), (a1, b1) = q['ends']
            if horiz and abs(b0 - b1) < 1e-3 and abs(b0 - y0) < 0.2 and p['geom'].distance(q['geom']) < TOUCH:
                return True
            if not horiz and abs(a0 - a1) < 1e-3 and abs(a0 - x0) < 0.2 and p['geom'].distance(q['geom']) < TOUCH:
                return True
        return False
    lines = list(long_lines)
    for p in short_axis:
        if collinear_with_long(p):
            lines.append(p); continue
        host = next((sym for sym in symbols if sym['role'] == 'symbol' and sym['geom'].distance(p['geom']) < TOUCH), None)
        if host is not None:
            host['prims'].append(p); host['geom'] = unary_union([q['geom'] for q in host['prims']])
        else:
            lines.append(p)
    caps = []
    # 아주 작은 기호가 다른 기호에 붙어 있으면 합친다 (밸브의 점 등)
    symbols = symbols + caps
    merged = True
    while merged:
        merged = False
        for a in symbols:
            if box(*a['geom'].bounds).area >= 2 or a['role'] != 'symbol':
                continue
            for b in symbols:
                if b is a or b['role'] != 'symbol' or a['geom'].distance(b['geom']) >= 1.0:
                    continue
                b['prims'].extend(a['prims']); b['geom'] = unary_union([q['geom'] for q in b['prims']])
                symbols.remove(a); merged = True; break
            if merged:
                break
    nodes = shapes + symbols
    for s in nodes:
        s['geom'] = unary_union([p['geom'] for p in s['prims']])
        s['bbox'] = [round(v, 2) for v in s['geom'].bounds]
    return nodes, lines

# ---------- 5. 선 병합, 절단, 연결 ----------
def merge_collinear(lines):
    """같은 축 위에서 겹치거나 맞닿는 직선을 하나로 합친다."""
    groups = collections.defaultdict(list)
    for l in lines:
        (x0, y0), (x1, y1) = l['ends']
        if abs(y0 - y1) < 1e-3:
            groups[('h', round(y0, 1))].append((min(x0, x1), max(x0, x1), l))
        else:
            groups[('v', round(x0, 1))].append((min(y0, y1), max(y0, y1), l))
    merged = []
    for (o, c), ivs in groups.items():
        ivs.sort(key=lambda iv: (iv[0], iv[1]))
        cur = list(ivs[0][:2]); members = [ivs[0][2]]
        for a, b, l in ivs[1:]:
            if a <= cur[1] + TOUCH:
                cur[1] = max(cur[1], b); members.append(l)
            else:
                merged.append((o, c, cur, members)); cur = [a, b]; members = [l]
        merged.append((o, c, cur, members))
    out = []
    for o, c, (a, b), members in merged:
        ends = [(a, c), (b, c)] if o == 'h' else [(c, a), (c, b)]
        out.append(dict(ends=ends, geom=LineString(ends), width=max(m['width'] for m in members),
                        dashed=any(m['dashed'] for m in members)))
    return out

def connect(nodes, lines):
    lines = merge_collinear(lines)
    # 긴 선에 직각으로 걸린 짧은 선: 선 끝에 있으면 끝막음 기호, 중간에 있으면 표시(노즐 표시, 플랜지 등)
    def ends_free(l):
        for e in l['ends']:
            for q in lines:
                if q is not l and any(math.dist(e, f) < TOUCH for f in q['ends']):
                    return False
            if any(n['geom'].distance(SPoint(e)) < TOUCH for n in nodes):
                return False
        return True
    keep = []
    for l in lines:
        if l['geom'].length < LONG or (l['geom'].length < 2 * LONG and ends_free(l)):
            (x0, y0), (x1, y1) = l['ends']
            horiz = abs(y0 - y1) < 1e-3
            mid = l['geom'].interpolate(0.5, normalized=True)
            host = None
            for q in lines:
                if q is l or q['geom'].length <= l['geom'].length:
                    continue
                (a0, b0), (a1, b1) = q['ends']
                if (abs(b0 - b1) < 1e-3) != horiz and q['geom'].distance(mid) < TOUCH:
                    host = q; break
            if host is not None:
                d = host['geom'].project(mid)
                at_end = d < TOUCH or d > host['geom'].length - TOUCH
                prim = dict(kind='line', geom=l['geom'], ends=l['ends'], length=l['geom'].length, axis=True)
                nodes.append(dict(role='symbol' if at_end else 'mark', prims=[prim], geom=l['geom'],
                                  bbox=[round(v, 2) for v in l['geom'].bounds], cap=at_end))
                continue
        keep.append(l)
    lines = keep
    for i, l in enumerate(lines):
        l['lid'] = i
    def touching_nodes(geom, tol=TOUCH):
        out = []
        for ni, n in enumerate(nodes):
            if n['role'] == 'mark':
                continue
            b = n['bbox']; g = geom.bounds
            if g[0] > b[2] + tol or g[2] < b[0] - tol or g[1] > b[3] + tol or g[3] < b[1] - tol:
                continue
            if n['geom'].distance(geom) < tol:
                out.append(ni)
        return out
    # 선 위에 놓인 기호(인라인 밸브 등)와 다른 선의 끝점(분기)에서 선을 자른다
    junctions, arrows_on = [], collections.defaultdict(list)
    pieces = []
    for l in lines:
        cuts = []
        for ni in touching_nodes(l['geom']):
            n = nodes[ni]
            c = n['geom'].centroid
            d = l['geom'].project(c)
            if n['role'] == 'mark':
                continue
            interior = TOUCH < d < l['geom'].length - TOUCH
            if n.get('direction') and interior:
                n['role'] = 'arrow'; arrows_on[l['lid']].append(ni); continue
            if interior:
                cuts.append((d, ('N', ni)))
        for l2 in lines:
            if l2 is l:
                continue
            for p in l2['ends']:
                sp = SPoint(p)
                if l['geom'].distance(sp) < TOUCH and TOUCH < l['geom'].project(sp) < l['geom'].length - TOUCH:
                    jid = next((j for j, jn in enumerate(junctions) if math.dist(jn['pt'], p) < TOUCH), None)
                    if jid is None:
                        junctions.append(dict(pt=p)); jid = len(junctions) - 1
                    cuts.append((l['geom'].project(sp), ('J', jid)))
        cuts.sort()
        pts = [(0.0, None)] + cuts + [(l['geom'].length, None)]
        for (d0, v0), (d1, v1) in zip(pts, pts[1:]):
            if d1 - d0 < 1e-6:
                continue
            a, b = l['geom'].interpolate(d0), l['geom'].interpolate(d1)
            pieces.append(dict(ends=[(a.x, a.y), (b.x, b.y)], va=v0, vb=v1, src=l['lid'],
                               width=l['width'], dashed=l['dashed']))
    all_ends = [(pc, k) for pc in pieces for k in (0, 1)]
    corners = []
    def corner_key(pt):
        # 모서리 꼭짓점은 TOUCH 안의 기존 꼭짓점에 맞춰 같은 키를 쓴다(두 끝의 좌표가 조금 달라도 하나의 모서리)
        for c in corners:
            if math.dist(c, pt) < TOUCH:
                return ('C', c)
        c = (round(pt[0], 1), round(pt[1], 1)); corners.append(c)
        return ('C', c)
    def vertex_of(pc, k):
        fixed = pc['va'] if k == 0 else pc['vb']
        if fixed:
            return fixed
        pt = pc['ends'][k]
        tn = touching_nodes(SPoint(pt))
        if tn:
            return ('N', min(tn, key=lambda ni: nodes[ni]['geom'].distance(SPoint(pt))))
        for j, jn in enumerate(junctions):
            if math.dist(jn['pt'], pt) < TOUCH:
                return ('J', j)
        for pc2, k2 in all_ends:
            if pc2 is not pc and math.dist(pc2['ends'][k2], pt) < TOUCH:
                return corner_key(pt)                               # 모서리
        # 선 방향으로 조금 연장했을 때 요소에 닿으면 간격이 있는 연결 후보로 본다
        other = pc['ends'][1 - k]
        L = math.dist(pt, other)
        if L > 0:
            ux, uy = (pt[0] - other[0]) / L, (pt[1] - other[1]) / L
            ext = LineString([pt, (pt[0] + ux * GAP, pt[1] + uy * GAP)])
            tn = touching_nodes(ext)
            if tn:
                ni = min(tn, key=lambda i: nodes[i]['geom'].distance(SPoint(pt)))
                pc.setdefault('gap', {})[k] = round(nodes[ni]['geom'].distance(SPoint(pt)), 2)
                return ('N', ni)
            for pc2, k2 in all_ends:
                if pc2 is not pc and ext.distance(SPoint(pc2['ends'][k2])) < TOUCH:
                    pc.setdefault('gap', {})[k] = round(math.dist(pt, pc2['ends'][k2]), 2)
                    pc2.setdefault('gap', {})[k2] = pc['gap'][k]
                    q = pc2['ends'][k2]
                    return corner_key(((pt[0] + q[0]) / 2, (pt[1] + q[1]) / 2))
        return ('O', (round(pt[0], 1), round(pt[1], 1)))           # 열린 끝
    adj = collections.defaultdict(list)
    for pc in pieces:
        pc['v'] = (vertex_of(pc, 0), vertex_of(pc, 1))
        if pc['v'][0] != pc['v'][1]:
            adj[pc['v'][0]].append((pc['v'][1], pc)); adj[pc['v'][1]].append((pc['v'][0], pc))
    runs, seen = [], set()
    for start in [v for v in adj if v[0] != 'C']:
        for nxt, pc in adj[start]:
            if id(pc) in seen:
                continue
            seen.add(id(pc))
            k0 = 0 if pc['v'][0] == start else 1
            coords = [pc['ends'][k0], pc['ends'][1 - k0]]
            cur, prev = nxt, pc
            widths, dashed, arrows = [pc['width']], pc['dashed'], list(arrows_on.get(pc['src'], []))
            while cur[0] == 'C':
                outs = [(v, q) for v, q in adj[cur] if q is not prev]
                if len(outs) != 1:
                    break
                cur, prev = outs[0]; seen.add(id(prev))
                k = 0 if math.dist(prev['ends'][0], coords[-1]) <= math.dist(prev['ends'][1], coords[-1]) else 1
                coords.append(prev['ends'][k]) if math.dist(prev['ends'][k], coords[-1]) > TOUCH else None
                coords.append(prev['ends'][1 - k]); widths.append(prev['width']); dashed |= prev['dashed']
                arrows += arrows_on.get(prev['src'], [])
            gaps = [g for q in (pc, prev) for g in q.get('gap', {}).values()]
            runs.append(dict(a=start, b=cur, coords=[(round(x, 2), round(y, 2)) for x, y in coords],
                             width=max(widths), dashed=dashed, arrows=sorted(set(arrows)), gap=max(gaps) if gaps else 0))
    # 잡음 제거: 열린 끝이 있는 아주 짧은 구간, 양 끝이 모두 열린 짧은 구간
    def length(r):
        return sum(math.dist(p, q) for p, q in zip(r['coords'], r['coords'][1:]))
    runs = [r for r in runs if r['a'] != r['b']
            and not ((r['a'][0] == 'O' or r['b'][0] == 'O') and length(r) < 2.5)
            and not (r['a'][0] == 'O' and r['b'][0] == 'O' and length(r) < LONG)]
    return runs, junctions

# ---------- 6. 문자 연결과 역할 ----------
TAG_EQUIP = re.compile(r'^[A-Z]{1,2} ?\d{4}$')
FAR_TAG = 30.0      # 장비 밖에 따로 적힌 장비 태그를 가장 가까운 무명 장비에 붙이는 한계 거리(mm)
TAG_INSTR = re.compile(r'^[A-Z]{2,5}$')
TAG_LOOP = re.compile(r'^\d{4}\.\d{2}$')
TAG_LINE = re.compile(r'^[A-Z]{2,3}[a-z]? \d{5} ')
def attach_texts(texts, nodes, runs):
    labels = []
    for t in texts:
        tb = text_bbox(t)
        best, bd = None, max(NEAR_NODE, 1.5 * t['size'])
        for ni, n in enumerate(nodes):
            if n['role'] in ('arrow', 'mark'):
                continue
            d = box(*n['bbox']).distance(tb)
            if d < bd:
                best, bd = ni, d
        rbest, rd = None, NEAR_RUN
        for ri, r in enumerate(runs):
            g = LineString(r['coords'])
            d = g.distance(tb)
            (x0, y0), (x1, y1) = r['coords'][0], r['coords'][-1]
            horiz = abs(y1 - y0) <= abs(x1 - x0)
            if d < rd and (t['angle'] == 0) == horiz:
                rbest, rd = ri, d
        if TAG_LINE.match(t['text']) and rbest is not None:
            owner = ('run', rbest, round(rd, 2))
        elif best is not None:
            owner = ('node', best, round(bd, 2))
        elif rbest is not None:
            owner = ('run', rbest, round(rd, 2))
        else:
            owner = None
        labels.append(dict(text=t['text'], x=round(t['x'], 2), y=round(t['y'], 2), angle=t['angle'],
                           bbox=[round(v, 2) for v in tb.bounds], owner=owner))
    return labels

def arrow_direction(n):
    if len(n['prims']) != 2 or any(p['kind'] != 'line' for p in n['prims']):
        return None
    (a0, a1), (b0, b1) = n['prims'][0]['ends'], n['prims'][1]['ends']
    shared = [p for p in (a0, a1) if min(math.dist(p, b0), math.dist(p, b1)) < TOUCH]
    others = [p for p in (a0, a1, b0, b1) if shared and math.dist(p, shared[0]) >= TOUCH]
    if not shared or len(others) < 2:
        return None
    apex = shared[0]
    mx, my = sum(p[0] for p in others) / len(others), sum(p[1] for p in others) / len(others)
    v = (apex[0] - mx, apex[1] - my); L = math.hypot(*v)
    return (round(v[0] / L, 2), round(v[1] / L, 2)) if L > 0 else None

def main(svg_path, out_prefix):
    W, H, prims, texts = load_primitives(svg_path)
    prims, texts, tables = remove_frame_and_tables(W, H, prims, texts)
    nodes, lines = build_nodes(prims)
    return assemble(W, H, nodes, lines, texts, tables, out_prefix, n_prims=len(prims))

def assemble(W, H, nodes, lines, texts, tables, out_prefix, n_prims=0, signal_ratio=None):
    """요소(nodes)와 선(lines)에서 연결을 찾고 문자를 붙여 그래프 파일을 쓴다. 벡터·래스터 경로가 공유함."""
    global GAP
    # 간격 허용치는 도면의 주 배관 굵기에 비례(굵은 선으로 그린 도면은 기호도 크고 간격도 큼)
    wc0 = collections.Counter(round(l['width'], 2) for l in lines if l['length'] >= LONG)
    pw0 = max([w for w, c in wc0.items() if c >= 3] or [0.5])
    GAP = max(5.0, 10.0 * pw0)
    for n in nodes:                                   # 꺾쇠 두 선은 방향 후보: 선이 관통하면 화살표
        if n['role'] == 'symbol':
            n['direction'] = arrow_direction(n)
    runs, junctions = connect(nodes, lines)
    # 끝막음 기호가 어디에도 닿지 않으면 가까운 요소와 간격 연결 후보를 만든다
    linked = collections.defaultdict(set)
    for r in runs:
        if r['a'][0] == 'N' and r['b'][0] == 'N':
            linked[r['a'][1]].add(r['b'][1]); linked[r['b'][1]].add(r['a'][1])
    for i, n in enumerate(nodes):
        if n.get('cap'):
            cands = [(n['geom'].distance(m['geom']), j) for j, m in enumerate(nodes)
                     if j != i and j not in linked[i] and m['role'] not in ('mark', 'arrow')]
            d, j = min(cands) if cands else (None, None)
            if d is not None and d < 1.5:
                c, o = n['geom'].centroid, nodes[j]['geom'].interpolate(nodes[j]['geom'].project(n['geom'].centroid))
                runs.append(dict(a=('N', i), b=('N', j), coords=[(round(c.x, 2), round(c.y, 2)), (round(o.x, 2), round(o.y, 2))],
                                 width=0.25, dashed=False, arrows=[], gap=round(d, 2)))
    labels = attach_texts(texts, nodes, runs)
    deg = collections.Counter()
    for r in runs:
        for v in (r['a'], r['b']):
            if v[0] == 'N':
                deg[v[1]] += 1
    for i, n in enumerate(nodes):
        n['texts'] = [l['text'] for l in labels if l['owner'] and l['owner'][0] == 'node' and l['owner'][1] == i]
    # 도형에 맞닿은 작은 기호는 그 도형의 노즐(접속구)로 보고, 연결 수를 도형에 합산한다
    for i, n in enumerate(nodes):
        if n['role'] == 'symbol' and box(*n['bbox']).area < 12:
            for j, m in enumerate(nodes):
                if m['role'] == 'shape' and n['geom'].distance(m['geom']) < TOUCH:
                    n['role'], n['attached_to'] = 'nozzle', j
                    deg[j] += deg[i]
                    break
    # 도형에서 나온 짧은 토막 끝의 끝막음 기호는 그 도형의 접속구
    for r in runs:
        va, vb = r['a'], r['b']
        if va[0] == 'N' and vb[0] == 'N':
            L = sum(math.dist(p, q) for p, q in zip(r['coords'], r['coords'][1:]))
            for x, y in ((va[1], vb[1]), (vb[1], va[1])):
                if nodes[x].get('cap') and nodes[y]['role'] == 'shape' and L < LONG and deg[x] == 1:
                    nodes[x]['role'], nodes[x]['attached_to'] = 'nozzle', y
    for i, n in enumerate(nodes):
        n['degree'] = deg[i]
        if n['role'] in ('arrow', 'mark', 'nozzle'):
            continue
        n['direction'] = None
        if any(TAG_EQUIP.match(t) for t in n['texts']):
            n['role'] = 'equipment'
        elif any(TAG_INSTR.match(t) for t in n['texts']) and any(TAG_LOOP.match(t) for t in n['texts']):
            n['role'] = 'instrument'
        elif n['role'] == 'shape' and deg[i] == 0 and n['texts']:
            n['role'] = 'note'
        elif n['role'] == 'shape':
            n['role'] = 'equipment' if deg[i] >= 2 and box(*n['bbox']).area >= 30 else 'symbol'
    # 장비 밖에 따로 적힌 장비 태그(예: 탑 옆의 K 2750)는 태그가 없는 가장 가까운 장비의 문자로 붙인다
    for l in labels:
        if l['owner'] or not TAG_EQUIP.match(l['text']):
            continue
        tb = box(*l['bbox'])
        cands = [(tb.distance(box(*m['bbox'])), j) for j, m in enumerate(nodes)
                 if m['role'] == 'equipment' and not any(TAG_EQUIP.match(t) for t in m['texts'])]
        d, j = min(cands) if cands else (None, None)
        if d is not None and d < FAR_TAG:
            l['owner'] = ('node', j, round(d, 2))
            nodes[j]['texts'].insert(0, l['text'])
    for i, n in enumerate(nodes):                     # 붙어 있는 기호의 문자는 소속 요소의 문자로 합친다
        if 'attached_to' in n:
            nodes[n['attached_to']]['texts'] += [t for t in n['texts'] if t not in nodes[n['attached_to']]['texts']]
    for i, n in enumerate(nodes):                     # 주석 상자는 가장 가까운 요소에 대한 설명으로 본다
        if n['role'] == 'note':
            cands = [(box(*n['bbox']).distance(box(*m['bbox'])), j) for j, m in enumerate(nodes)
                     if j != i and m['role'] not in ('note', 'mark', 'arrow')]
            d, j = min(cands) if cands else (None, None)
            if d is not None and d < 1.5 * NEAR_NODE:
                n['annotates'] = j
    # 신호선: 점선이거나 가장 굵은 선 부류의 절반보다 가는 선 (굵기 기준은 도면마다 상대적으로 정함)
    wc = collections.Counter(round(r['width'], 2) for r in runs)
    pipe_w = max([w for w, c in wc.items() if c >= 3] or [max(wc) if wc else 0.5])
    def run_kind(r):
        return 'signal' if r['dashed'] or r['width'] < (signal_ratio or SIGNAL_RATIO) * pipe_w else 'pipe'
    def vname(v):
        return {'N': f"n{v[1]}", 'J': f"j{v[1]}"}.get(v[0], f"open@{v[1]}")
    out = dict(
        page=[W, H],
        nodes=[dict(id=f"n{i}", role=n['role'], bbox=n['bbox'], texts=n['texts'], primitives=len(n['prims']),
                    degree=n['degree'], attached_to=(f"n{n['attached_to']}" if 'attached_to' in n else None),
                    direction=n.get('direction'), annotates=(f"n{n['annotates']}" if 'annotates' in n else None))
               for i, n in enumerate(nodes)],
        junctions=[dict(id=f"j{i}", pt=[round(v, 2) for v in j['pt']]) for i, j in enumerate(junctions)],
        runs=[dict(id=f"r{i}", a=vname(r['a']), b=vname(r['b']), coords=r['coords'], width=r['width'],
                   dashed=r['dashed'], kind=run_kind(r), gap=r['gap'],
                   arrows=[f"n{a}" for a in r['arrows']],
                   texts=[l['text'] for l in labels if l['owner'] and l['owner'][0] == 'run' and l['owner'][1] == i])
              for i, r in enumerate(runs)],
        labels=labels, tables=tables)
    out['counts'] = dict(primitives=n_prims, texts=len(texts), nodes=len(nodes), runs=len(runs),
                         junctions=len(junctions), tables=len(tables))
    json.dump(out, open(out_prefix + '.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out['counts']), collections.Counter(n['role'] for n in out['nodes']))
    return out

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
