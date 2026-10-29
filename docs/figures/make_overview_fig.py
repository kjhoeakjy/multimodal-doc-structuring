#!/usr/bin/env python3
"""처리 흐름 도식(가로형 1600x900). 입력 도면에서 출력(답변과 근거)까지를 실제 추출 결과의 그림 요소로 보임.
실행: python3 make_overview_fig.py > 파이프라인-전체-그림.svg"""
import json, re, math, random, html, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
svg_src = open(os.path.join(ROOT, 'examples/public-documents/pid/input/C01.svg'), encoding='utf-8').read()
G = json.load(open(os.path.join(ROOT, 'examples/dexpi-reference-pid/output/graph.json'), encoding='utf-8'))

W, H = 1600, 900
ACC = "#1F4FD8"; INK = "#111111"; GR = "#6B6B6B"; LINE = "#C9CCD2"; FILL = "#F4F5F7"
EQ, SYM, INS, PIPE, SIG, JCT, TBL = "#C8322E", "#1F4FD8", "#7A2BD1", "#1E8E57", "#2F80ED", "#E0A400", "#9AA0A6"
C_LINE, C_CURVE, C_ARC, C_TEXT = "#2B6CB0", "#C05621", "#6B46C1", "#2F855A"
FONT = "Pretendard, 'Noto Sans KR', sans-serif"; MONO = "'JetBrains Mono', 'DejaVu Sans Mono', monospace"
out = []

def t(x, y, s, size=13, w=400, color=INK, anchor="start", ls=None, mono=False):
    extra = f' letter-spacing="{ls}"' if ls else ""
    fam = f' font-family="{MONO}"' if mono else ""
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{color}" text-anchor="{anchor}"{extra}{fam}>{html.escape(s)}</text>')
def hline(x0, x1, y, color=LINE, sw=1): out.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{color}" stroke-width="{sw}"/>')
def arrow(x0, y0, x1, y1, color=INK, sw=1.4): out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{color}" stroke-width="{sw}" marker-end="url(#ah)"/>')
def rect(x, y, w, h, stroke=INK, fill="none", sw=1, dash=None, rx=0):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{d}/>')

# ---- 도면 요소(색 지정 가능한 복사본) ----
prims = []
for ln in svg_src.splitlines():
    s = ln.strip()
    if s.startswith('<path'):
        kind = 'curve' if ' A ' in s else 'line'
    elif s.startswith('<ellipse'): kind = 'arc'
    elif s.startswith('<text'): kind = 'text'
    else: continue
    prims.append((kind, s))
def drawing(colors, sw=0.25, text_on=True):
    buf = []
    for kind, s in prims:
        if kind == 'text' and not text_on: continue
        c = colors.get(kind, INK)
        if kind == 'text':
            s2 = s.replace('font-family="Calibri"', f'font-family="{FONT}" fill="{c}"')
        else:
            s2 = s.replace('stroke="black"', f'stroke="{c}"').replace('stroke-width="0.25"', f'stroke-width="{sw}"')
        buf.append(s2)
    return '\n'.join(buf)
MONO_D = drawing({'line': INK, 'curve': INK, 'arc': INK, 'text': INK})
TYPED_D = drawing({'line': C_LINE, 'curve': C_CURVE, 'arc': C_ARC, 'text': C_TEXT}, sw=0.35)
DIM_D = drawing({'line': '#C4C8CF', 'curve': '#C4C8CF', 'arc': '#C4C8CF', 'text': '#A9AEB6'})

def crop(x, y, w, h, vb, body, border=True):
    if border: rect(x, y, w, h, LINE, "#FFFFFF")
    out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}" preserveAspectRatio="xMidYMid meet">{body}</svg>')

nodes = G['nodes']; runs = G['runs']; juncs = G['junctions']; labels = G['labels']
nid = {n['id']: n for n in nodes}; jid = {j['id']: j for j in juncs}
def center(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
def pos(v): return center(nid[v]['bbox']) if v in nid else tuple(jid[v]['pt'])

def overlay(hl=None, with_labels=False):
    col = {'equipment': EQ, 'symbol': SYM, 'instrument': INS, 'nozzle': SYM, 'note': INS}
    b = []
    for r in runs:
        pts = ' '.join(f'{x},{y}' for x, y in r['coords'])
        c = PIPE if r['kind'] == 'pipe' else SIG
        b.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="0.9" stroke-linecap="round" stroke-linejoin="round"{" stroke-dasharray=\"1 0.8\"" if r["gap"] else ""}/>')
    for n in nodes:
        if n['role'] not in col: continue
        x0, y0, x1, y1 = n['bbox']
        b.append(f'<rect x="{x0-.6}" y="{y0-.6}" width="{x1-x0+1.2}" height="{y1-y0+1.2}" rx=".4" fill="none" stroke="{col[n["role"]]}" stroke-width="0.55"/>')
    for j in juncs:
        b.append(f'<circle cx="{j["pt"][0]}" cy="{j["pt"][1]}" r="1.1" fill="{JCT}" stroke="#fff" stroke-width=".3"/>')
    if with_labels:
        for l in labels:
            o = l['owner']
            if not o or o[0] != 'node': continue
            c = center(l['bbox']); tc = center(nodes[o[1]]['bbox'])
            b.append(f'<line x1="{c[0]}" y1="{c[1]}" x2="{tc[0]}" y2="{tc[1]}" stroke="{GR}" stroke-width=".22"/>')
    if hl:
        for v in hl['nodes']:
            x0, y0, x1, y1 = nid[v]['bbox']
            b.append(f'<rect x="{x0-1.2}" y="{y0-1.2}" width="{x1-x0+2.4}" height="{y1-y0+2.4}" rx=".6" fill="none" stroke="{ACC}" stroke-width="1.2"/>')
        for rid in hl['runs']:
            r = next(x for x in runs if x['id'] == rid)
            pts = ' '.join(f'{x},{y}' for x, y in r['coords'])
            b.append(f'<polyline points="{pts}" fill="none" stroke="{ACC}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>')
    return '\n'.join(b)

# ---- 그래프 배치 ----
gnodes = [n['id'] for n in nodes if n['role'] in ('equipment', 'instrument', 'symbol', 'nozzle', 'note') and (n['degree'] > 0 or n['role'] in ('equipment', 'instrument'))] + [j['id'] for j in juncs]
gset = set(gnodes); edges = [(r['a'], r['b'], r) for r in runs if r['a'] in gset and r['b'] in gset]
random.seed(3); P = {v: list(pos(v)) for v in gnodes}; k = 14.0
for it in range(260):
    temp = 6.0 * (1 - it / 260) + 0.3; disp = {v: [0.0, 0.0] for v in gnodes}
    for i, a in enumerate(gnodes):
        for b_ in gnodes[i + 1:]:
            dx = P[a][0] - P[b_][0]; dy = P[a][1] - P[b_][1]; d = math.hypot(dx, dy) + 1e-3; f = k * k / d
            disp[a][0] += dx / d * f; disp[a][1] += dy / d * f; disp[b_][0] -= dx / d * f; disp[b_][1] -= dy / d * f
    for a, b_, _ in edges:
        dx = P[a][0] - P[b_][0]; dy = P[a][1] - P[b_][1]; d = math.hypot(dx, dy) + 1e-3; f = d * d / k
        disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f; disp[b_][0] += dx / d * f; disp[b_][1] += dy / d * f
    for v in gnodes:
        dx, dy = disp[v]; d = math.hypot(dx, dy) + 1e-3; P[v][0] += dx / d * min(d, temp); P[v][1] += dy / d * min(d, temp)
xs = [p[0] for p in P.values()]; ys = [p[1] for p in P.values()]
def graph_pic(x, y, w, h, hl_nodes=(), hl_edges=(), names=True):
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    L = {v: (x + 14 + (p[0] - x0) / (x1 - x0) * (w - 28), y + 12 + (p[1] - y0) / (y1 - y0) * (h - 24)) for v, p in P.items()}
    col = {'equipment': EQ, 'instrument': INS, 'symbol': SYM, 'nozzle': SYM, 'note': INS}
    for a, b_, r in edges:
        c = ACC if r['id'] in hl_edges else (PIPE if r['kind'] == 'pipe' else SIG)
        sw = 2.2 if r['id'] in hl_edges else 1.1
        out.append(f'<line x1="{L[a][0]:.1f}" y1="{L[a][1]:.1f}" x2="{L[b_][0]:.1f}" y2="{L[b_][1]:.1f}" stroke="{c}" stroke-width="{sw}"{" stroke-dasharray=\"3 2\"" if r["kind"]=="signal" else ""}/>')
    for v in gnodes:
        role = nid[v]['role'] if v in nid else 'junction'
        r_ = {'equipment': 7, 'instrument': 5.5, 'junction': 2.5}.get(role, 3.5)
        c = col.get(role, JCT)
        if v in hl_nodes:
            out.append(f'<circle cx="{L[v][0]:.1f}" cy="{L[v][1]:.1f}" r="{r_+4}" fill="none" stroke="{ACC}" stroke-width="1.5"/>')
        out.append(f'<circle cx="{L[v][0]:.1f}" cy="{L[v][1]:.1f}" r="{r_}" fill="{c}"/>')
        if names and role in ('equipment', 'instrument'):
            nm = nid[v]['texts'][0] if nid[v]['texts'] else ''
            t(L[v][0] + r_ + 3, L[v][1] + 3.5, nm, 9, 500, INK, mono=True)
    return L

# ================= 구성 =================
t(50, 50, "기술 도면의 관계 그래프 구조화와 텍스트 LLM 연계", 24, 600, ls="-0.5")
t(1550, 50, "폐쇄망 · CPU · 생성형 VLM 미사용 · 기존 텍스트 LLM", 13, 400, GR, "end")
hline(50, 1550, 66, INK, 1.2)

ZOOM = (176, 72, 158, 112)
px = [50, 345, 640, 935, 1230]; pw = 265; py = 112; ph = 190
heads = [("입력", "벡터 PDF · CAD · 스캔"), ("1 시각 요소 추출", "직선 · 곡선 · 타원 · 문자"), ("2 관계 그래프", "접속 · 분기 · 포함 · 지시"), ("3 근거 연결 · 색인", "좌표 · 그래프 텍스트 · 임베딩"), ("4 텍스트 LLM", "부분 그래프 → 답변 · 근거")]
for i, (h1, h2) in enumerate(heads):
    t(px[i], py - 22, h1, 15, 600, ACC if i in (2,) else INK)
    t(px[i] + pw, py - 22, h2, 11.5, 400, GR, "end")
    if i < 4: arrow(px[i] + pw + 8, py + ph / 2, px[i + 1] - 8, py + ph / 2)

# 입력: 전체 도면 + 스캔
crop(px[0], py, pw, ph, (0, 0, 420, 297), MONO_D)
t(px[0] + 6, py + ph - 8, "A3 420 × 297 mm", 10, 400, GR)
# 1: 요소 유형별 색
crop(px[1], py, pw, ph, ZOOM, TYPED_D)
# 2: 겹층 + 그래프
crop(px[2], py, pw, ph, ZOOM, DIM_D + overlay(with_labels=False))
# 3: 좌표가 붙은 요소
hl_q = {'nodes': ['n25'], 'runs': []}
crop(px[3], py, pw, ph, (236, 140, 44, 31), DIM_D + overlay(hl=hl_q))
out.append(f'<rect x="{px[3]+8}" y="{py+8}" width="164" height="16" fill="{INK}" opacity=".9"/>')
t(px[3] + 12, py + 20, "n25 equipment P4712", 10, 500, "#FFFFFF", mono=True)
out.append(f'<rect x="{px[3]+8}" y="{py+26}" width="196" height="16" fill="{ACC}" opacity=".9"/>')
t(px[3] + 12, py + 38, "bbox 245.8 148.8 256.2 159.2", 10, 500, "#FFFFFF", mono=True)
# 4: 답변 근거 강조
hl_a = {'nodes': ['n25', 'n7', 'n4'], 'runs': ['r9', 'r10', 'r11', 'r13']}
crop(px[4], py, pw, ph, (236, 84, 60, 84), DIM_D + overlay(hl=hl_a))

# ---- 2단: 각 단계의 산출물 ----
y2 = 330
for i in range(5):
    hline(px[i], px[i] + pw, y2 - 14, LINE)
# 입력 경로 두 갈래
t(px[0], y2 + 6, "벡터", 12, 600); t(px[0] + 44, y2 + 6, "경로 · 문자 좌표", 11.5, 400, GR)
t(px[0], y2 + 28, "스캔", 12, 600); t(px[0] + 44, y2 + 28, "보정 → OCR → 선 · 윤곽", 11.5, 400, GR)
# 1: 유형 범례와 개수
cnt = {'line': sum(1 for k_, _ in prims if k_ == 'line'), 'curve': sum(1 for k_, _ in prims if k_ == 'curve'), 'arc': sum(1 for k_, _ in prims if k_ == 'arc'), 'text': sum(1 for k_, _ in prims if k_ == 'text')}
for j, (c, nm, n_) in enumerate([(C_LINE, "직선", cnt['line']), (C_CURVE, "곡선", cnt['curve']), (C_ARC, "타원", cnt['arc']), (C_TEXT, "문자", cnt['text'])]):
    yy = y2 + 6 + j * 22
    out.append(f'<rect x="{px[1]}" y="{yy-9}" width="10" height="10" fill="{c}"/>'); t(px[1] + 16, yy, nm, 12, 500); t(px[1] + 60, yy, str(n_), 12, 600, INK, mono=True)
t(px[1] + 110, y2 + 6, "mm 좌표 · 굵기 · 점선", 11.5, 400, GR)
t(px[1] + 110, y2 + 28, "색 · 식별자 미사용", 11.5, 400, GR)
# 2: 노드·간선 범례와 규칙 수치
leg = [(EQ, "장비 5"), (INS, "계기 4"), (SYM, "기호 19"), (PIPE, "배관 37"), (SIG, "신호선 7"), (JCT, "분기점 5")]
for j, (c, nm) in enumerate(leg):
    xx = px[2] + (j % 3) * 88; yy = y2 + 6 + (j // 3) * 22
    out.append(f'<rect x="{xx}" y="{yy-9}" width="10" height="10" fill="{c}"/>'); t(xx + 16, yy, nm, 12, 500)
t(px[2], y2 + 52, "접속 0.6 mm · 간격 후보 5 mm · 라벨 4 mm", 11.5, 400, GR)
# 3: 색인 네 갈래 그림
lanes = [("그래프 텍스트", "BM25"), ("태그", "완전 일치"), ("표 행", "텍스트"), ("쪽 · 그림", "이미지 임베딩")]
for j, (a, b_) in enumerate(lanes):
    yy = y2 + 6 + j * 22
    t(px[3], yy, a, 12, 500); arrow(px[3] + 96, yy - 4, px[3] + 126, yy - 4, GR, 1); t(px[3] + 132, yy, b_, 12, 400, GR)
# 임베딩 막대
for j in range(28):
    hh = 4 + abs(math.sin(j * 1.7) * 14 + math.cos(j * .9) * 4)
    out.append(f'<rect x="{px[3]+ j*4}" y="{y2 + 110 - hh}" width="3" height="{hh:.0f}" fill="{ACC}"/>')
t(px[3] + 120, y2 + 108, "밀집 벡터 (검색 전용)", 11, 400, GR)
# 4: 질의 흐름
t(px[4], y2 + 6, "질문", 12, 600); t(px[4] + 44, y2 + 6, "\"P4712 토출 측 연결\"", 11.5, 400, GR)
t(px[4], y2 + 28, "조회", 12, 600); t(px[4] + 44, y2 + 28, "P4712 → n25 → 3단계 부분 그래프", 11.5, 400, GR)
t(px[4], y2 + 50, "입력", 12, 600); t(px[4] + 44, y2 + 50, "그래프 텍스트 8줄 · 이미지 없음", 11.5, 400, GR)
t(px[4], y2 + 72, "출력", 12, 600); t(px[4] + 44, y2 + 72, "답변 + 근거 좌표", 11.5, 400, GR)

# ---- 3단: 그래프 전체와 직렬화, 질의 부분 그래프 ----
y3 = 470
hline(50, 1550, y3 - 10, INK, 1.2)
t(50, y3 + 12, "관계 그래프", 13, 600, GR, ls="1")
rect(50, y3 + 22, 560, 250, LINE, "#FFFFFF")
graph_pic(50, y3 + 22, 560, 250)
t(620, y3 + 12, "직렬화 (노드 · 구간 · 좌표)", 13, 600, GR, ls="1")
rect(620, y3 + 22, 450, 250, LINE, FILL)
ser = ["n25 equipment P4712 라벨 P4712|N1|50|N2|50", "    bbox (245.8,148.8,256.2,159.2)",
       "r9  pipe  A n25  B j2", "    경로 (256.2,154.0)→(265.0,154.0)",
       "r11 pipe  A j2   B n7[73KH12-25]", "r13 pipe  A j0   B n4[SV 104.01]", "    라벨 MNc 47125 73HG12 25",
       "r23 signal A n17[TICSA 4750.03] B n13", "    간격 4.05 mm (후보)"]
for j, s in enumerate(ser):
    t(634, y3 + 48 + j * 22, s, 11.5, 400, INK if not s.startswith('    ') else GR, mono=True)
t(634, y3 + 258, "모델 없음 · 0.7초", 11.5, 400, GR)
t(1080, y3 + 12, "질의 부분 그래프", 13, 600, GR, ls="1")
rect(1080, y3 + 22, 470, 250, LINE, "#FFFFFF")
graph_pic(1080, y3 + 22, 470, 250, hl_nodes=('n25', 'n3', 'n7', 'n4', 'n29', 'n2'), hl_edges=('r8', 'r9', 'r7', 'r10', 'r11', 'r6', 'r12', 'r13'), names=True)
t(1094, y3 + 258, "n25에서 3단계 · 간선 8", 11.5, 400, GR)

# ---- 하단: 실측 ----
y4 = 775
hline(50, 1550, y4, LINE)
stats = [("27/27", "벡터 · 정답 쌍"), ("60/62", "벡터 · 라벨 소속"), ("0.7초", "벡터 · 1장"), ("14/26", "래스터 200 dpi"), ("10/23", "스캔 열화"), ("64초", "래스터 · 1장 (OCR 44초)"), ("1", "신경망 모델 (OCR)"), ("0", "생성형 VLM")]
for j, (b_, s) in enumerate(stats):
    xx = 50 + j * 188
    t(xx, y4 + 44, b_, 26, 700, ACC if j == 0 else INK)
    t(xx, y4 + 64, s, 11.5, 400, GR)
t(50, y4 + 102, "자료 DEXPI 참조 P&ID C01V04 · 실측 CPU 4코어", 11, 400, GR)
t(1550, y4 + 102, "docs/figures/make_overview_fig.py", 11, 400, GR, "end")

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{INK}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>'''
print(svg)
