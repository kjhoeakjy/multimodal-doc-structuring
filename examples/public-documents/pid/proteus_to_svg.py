"""Proteus XML(DEXPI)의 도형 정보를 평면 SVG로 변환한다. 색·식별자는 넣지 않는다."""
import sys, math, xml.etree.ElementTree as ET

PRIMS = ('Line', 'PolyLine', 'Circle', 'Ellipse', 'TrimmedCurve', 'Shape', 'Text')
DASH = {'Dashed': '2 1', 'Dotted': '0.5 0.5', 'Dash Dot': '2 1 0.5 1', 'DashDot': '2 1 0.5 1',
        'Dash Dot Dot': '2 1 0.5 1 0.5 1', 'Long Dash': '4 1', 'Short Dash': '1 1', '2': '2 1', '3': '0.5 0.5'}
MIN_W = 0.05   # 이보다 가는 선(보이지 않는 중심선)은 그리지 않음

def num(v):
    r = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if r in ('', '-0') else r

def f(el, k, d=0.0):
    v = el.get(k)
    return float(v) if v not in (None, '') else d

def xy(el):
    return f(el, 'X'), f(el, 'Y')

def pres(el, inherit):
    p = el.find('Presentation')
    if p is None:
        return inherit
    w = p.get('LineWeight')
    return dict(w=float(w) if w else inherit['w'], lt=p.get('LineType', inherit['lt']))

def position(el):
    """Position 요소를 (location, 회전각)으로 읽는다."""
    pos = el.find('Position')
    if pos is None:
        return (0.0, 0.0), 0.0
    loc = pos.find('Location'); ref = pos.find('Reference')
    l = xy(loc) if loc is not None else (0.0, 0.0)
    a = math.atan2(f(ref, 'Y'), f(ref, 'X', 1.0)) if ref is not None else 0.0
    return l, a

def mat_mul(a, b):
    a0, a1, a2, a3, a4, a5 = a; b0, b1, b2, b3, b4, b5 = b
    return (a0*b0 + a2*b1, a1*b0 + a3*b1, a0*b2 + a2*b3, a1*b2 + a3*b3,
            a0*b4 + a2*b5 + a4, a1*b4 + a3*b5 + a5)

def instance_matrix(el):
    (lx, ly), a = position(el)
    sc = el.find('Scale')
    sx, sy = (f(sc, 'X', 1.0), f(sc, 'Y', 1.0)) if sc is not None else (1.0, 1.0)
    c, s = math.cos(a), math.sin(a)
    return (c*sx, s*sx, -s*sy, c*sy, lx, ly), (sx, sy)

def apply(m, p):
    return (m[0]*p[0] + m[2]*p[1] + m[4], m[1]*p[0] + m[3]*p[1] + m[5])

class Writer:
    def __init__(self, unit, H):
        self.unit, self.H, self.out = unit, H, []
        self.F = (unit, 0, 0, -unit, 0, H)   # 세계 좌표(mm 또는 m)를 SVG 좌표로

    def style(self, pr, sdiv=1.0):
        w = pr['w'] * self.unit / sdiv
        d = DASH.get(pr['lt'])
        return f'fill="none" stroke="black" stroke-width="{num(w)}"' + (f' stroke-dasharray="{d}"' if d else '')

    def factor(self, M):
        return math.sqrt(abs(M[0]*M[3] - M[1]*M[2]))

    def uniform(self, M):
        return abs(math.hypot(M[0], M[1]) - math.hypot(M[2], M[3])) < 1e-3 * max(1.0, math.hypot(M[0], M[1]))

    def ellipse(self, L, rx, ry, pr, M):
        """타원은 변환 행렬 대신 세계 좌표의 중심·반지름으로 쓴다(읽는 쪽이 행렬을 풀지 않아도 되게)."""
        cx, cy = L[4], L[5]
        ex, ey = rx * math.hypot(L[0], L[1]), ry * math.hypot(L[2], L[3])
        ang = math.degrees(math.atan2(L[1], L[0])) % 180
        if abs(ang - 90) < 1e-3:
            ex, ey = ey, ex
        elif ang > 1e-3:          # 비스듬한 타원은 호 두 개의 경로로 쓴다
            p0 = apply(L, (rx, 0)); p1 = apply(L, (-rx, 0))
            d = f'M {num(p0[0])} {num(p0[1])} A {num(ex)} {num(ey)} {num(ang)} 1 0 {num(p1[0])} {num(p1[1])} A {num(ex)} {num(ey)} {num(ang)} 1 0 {num(p0[0])} {num(p0[1])} Z'
            self.out.append(f'<path d="{d}" {self.style(pr)}/>'); return
        self.out.append(f'<ellipse cx="{num(cx)}" cy="{num(cy)}" rx="{num(ex)}" ry="{num(ey)}" {self.style(pr)}/>')

    def sampled(self, L, rx, ry, a0, a1, pr, closed):
        n = max(8, int(24 * abs(a1 - a0) / (2*math.pi)))
        pts = [apply(L, (rx*math.cos(a0 + (a1 - a0)*i/n), ry*math.sin(a0 + (a1 - a0)*i/n))) for i in range(n + 1)]
        d = 'M ' + ' L '.join(f'{num(x)} {num(y)}' for x, y in pts) + (' Z' if closed else '')
        self.out.append(f'<path d="{d}" {self.style(pr)}/>')

    def prim(self, el, pr, M, sdiv):
        """M: 국소 좌표를 SVG 좌표로 보내는 행렬."""
        pr = pres(el, pr)
        if pr['w'] * self.unit < MIN_W and el.tag != 'Text':
            return
        t = el.tag
        if t in ('Line', 'PolyLine', 'Shape', 'CenterLine'):
            pts = [apply(M, xy(c)) for c in el.findall('Coordinate')]
            if len(pts) < 2 or any(abs(v) > 1e6 for p in pts for v in p):
                return
            d = 'M ' + ' L '.join(f'{num(x)} {num(y)}' for x, y in pts) + (' Z' if t == 'Shape' else '')
            self.out.append(f'<path d="{d}" {self.style(pr)}/>')
        elif t in ('Circle', 'Ellipse'):
            (cx, cy), a = position(el)
            rx = f(el, 'Radius') if t == 'Circle' else f(el, 'PrimaryAxis') / 2
            ry = rx if t == 'Circle' else f(el, 'SecondaryAxis') / 2
            if not all(math.isfinite(v) and abs(v) < 1e6 for v in (cx, cy, rx, ry)):
                return
            c, s = math.cos(a), math.sin(a)
            L = mat_mul(M, (c, s, -s, c, cx, cy))
            if abs(L[4]) > 1e6 or abs(L[5]) > 1e6:
                return
            self.ellipse(L, rx, ry, pr, M)
        elif t == 'TrimmedCurve':
            base = el.find('Circle') if el.find('Circle') is not None else el.find('Ellipse')
            if base is None:
                return
            pr = pres(base, pr)
            (cx, cy), a = position(base)
            rx = f(base, 'Radius') if base.tag == 'Circle' else f(base, 'PrimaryAxis') / 2
            ry = rx if base.tag == 'Circle' else f(base, 'SecondaryAxis') / 2
            rx, ry = abs(rx), abs(ry)
            if not all(math.isfinite(v) for v in (cx, cy, rx, ry)) or rx == 0 or ry == 0:
                return
            a0, a1 = math.radians(f(el, 'StartAngle')), math.radians(f(el, 'EndAngle'))
            sweep = (a1 - a0) % (2*math.pi)
            if sweep < 1e-6:
                sweep = 2*math.pi
            if base.tag == 'Ellipse' and sweep > math.pi:
                # 타원 호를 쓰는 내보내기 도구는 시작각·끝각 사이의 짧은 호를 뜻함
                a0, a1 = a1, a0
                sweep = 2*math.pi - sweep
            c, s = math.cos(a), math.sin(a)
            L = mat_mul(M, (c, s, -s, c, cx, cy))
            if abs(L[4]) > 1e6 or abs(L[5]) > 1e6:
                return
            # 호를 국소 좌표에서 매개변수화해 SVG 호 명령으로 쓴다(국소 좌표계 안에서는 y가 위쪽이므로 sweep-flag 1)
            p0 = (rx*math.cos(a0), ry*math.sin(a0)); p1 = (rx*math.cos(a1), ry*math.sin(a1))
            if sweep >= 2*math.pi - 1e-6:
                self.ellipse(L, rx, ry, pr, M)
            else:
                large = 1 if sweep > math.pi else 0
                d = f'M {num(p0[0])} {num(p0[1])} A {num(rx)} {num(ry)} 0 {large} 1 {num(p1[0])} {num(p1[1])}'
                self.out.append(f'<path d="{d}" transform="matrix({" ".join(num(v) for v in L)})" {self.style(pr, self.factor(M))}/>')
        elif t == 'Text':
            s = el.get('String')
            if not s:
                return
            (tx, ty), _ = position(el)
            x, y = apply(M, (tx, ty))
            h = f(el, 'Height', 2.5) * self.unit
            ang = f(el, 'TextAngle')
            j = el.get('Justification', 'LeftBottom')
            anchor = 'middle' if j.startswith('Center') else ('end' if j.startswith('Right') else 'start')
            v = j[len('Center'):] if j.startswith('Center') else (j[len('Right'):] if j.startswith('Right') else j[len('Left'):])
            dy = 0.0 if v == 'Bottom' else (0.35*h if v == 'Center' else 0.7*h)
            s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            tr = f'translate({num(x)} {num(y)}) rotate({num(-ang)})'
            self.out.append(f'<text x="0" y="{num(dy)}" font-size="{num(h)}" font-family="Calibri" text-anchor="{anchor}" transform="{tr}">{s}</text>')

def collect_catalogue(root):
    cat = {}
    sc = root.find('ShapeCatalogue')
    if sc is None:
        return cat
    for ent in sc:
        name = ent.get('ComponentName') or ent.get('ID')
        cat[name] = ent
    return cat

def render(xml_path, svg_path):
    root = ET.parse(xml_path).getroot()
    unit = 1000.0 if (root.find('PlantInformation') is not None and root.find('PlantInformation').get('Units') == 'm') else 1.0
    ext = root.find('Drawing/Extent/Max')
    if ext is None:
        ext = root.find('Extent/Max')
    W, H = f(ext, 'X') * unit, f(ext, 'Y') * unit
    cat = collect_catalogue(root)
    wr = Writer(unit, H)
    default = dict(w=0.25 / unit, lt='Solid')
    n_inst = 0

    def draw_prims(parent, pr, M, sdiv, depth=0):
        for ch in parent:
            if ch.tag in PRIMS or ch.tag == 'CenterLine':
                wr.prim(ch, pr, M, sdiv)

    def walk(el, pr):
        if el.tag == 'ShapeCatalogue':
            return
        pr = pres(el, pr)
        name = el.get('ComponentName')
        if el.find('Position') is not None and name in cat and el.tag not in PRIMS:
            m, (sx, sy) = instance_matrix(el)
            if abs(sx) < 1e-6 or abs(sy) < 1e-6:
                return
            M = mat_mul(wr.F, m)
            sdiv = max(1e-6, (abs(sx) + abs(sy)) / 2)
            draw_prims(cat[name], pres(cat[name], pr), M, sdiv)
            nonlocal n_inst; n_inst += 1
        # 세계 좌표 도형
        draw_prims(el, pr, wr.F, 1.0)
        for ch in el:
            if ch.tag not in PRIMS and ch.tag != 'CenterLine':
                walk(ch, pr)
    walk(root, default)
    svg = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(W)}" height="{num(H)}" viewBox="0 0 {num(W)} {num(H)}">',
           f'<rect x="0" y="0" width="{num(W)}" height="{num(H)}" fill="white"/>'] + wr.out + ['</svg>']
    open(svg_path, 'w', encoding='utf-8').write('\n'.join(svg))
    print(f'{xml_path}: {W:.0f}x{H:.0f}, instances {n_inst}, elements {len(wr.out)}')

if __name__ == '__main__':
    render(sys.argv[1], sys.argv[2])
