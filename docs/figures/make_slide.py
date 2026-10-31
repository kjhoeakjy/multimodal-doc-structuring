#!/usr/bin/env python3
"""발표 1장(1600x900). 실제 추출 결과(DEXPI 참조 P&ID)로 원본, 요소·연결 복원, 구조화 결과를 보임.
실행: python make_slide.py  (같은 폴더에 1장-도면-관계-구조화.svg 생성)
글자 폭은 실제 글꼴로 측정해 칸을 넘는 줄이 있으면 오류로 중단함."""
import json, html, os, sys
from collections import deque
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
svg_src = open(os.path.join(ROOT, 'examples/public-documents/pid/input/C01.svg'), encoding='utf-8').read()
G = json.load(open(os.path.join(ROOT, 'examples/dexpi-reference-pid/output/graph.json'), encoding='utf-8'))
CTX = json.load(open(os.path.join(ROOT, 'examples/llm-qa/contexts.json'), encoding='utf-8'))['q003']

W, H = 1600, 900
ACC = "#1F4FD8"; INK = "#111111"; GR = "#5F6368"; LINE = "#CFD3D9"; FILL = "#F3F4F6"
EQ, SYM, INS, PIPE, SIG, JCT = "#C8322E", "#1F4FD8", "#7A2BD1", "#1E8E57", "#2F80ED", "#E0A400"
FONT = "'Noto Sans KR', 'Malgun Gothic', sans-serif"; MONO = "Consolas, 'Noto Sans KR', monospace"
FD = "C:/Windows/Fonts/"
_f = {}
def fnt(size, bold=False, mono=False):
    k = (size, bold, mono)
    if k not in _f:
        _f[k] = ImageFont.truetype(FD + ("consola.ttf" if mono else ("NotoSansKR-Bold.ttf" if bold else "NotoSansKR-Regular.ttf")), size)
    return _f[k]
def width(s, size, bold=False, mono=False):
    if mono:  # 고정폭 글꼴에 한글이 섞이면 한글은 대체 글꼴 폭으로 계산
        return sum(fnt(size, False, True).getlength(c) if ord(c) < 0x1100 else fnt(size).getlength(c) for c in s)
    return fnt(size, bold).getlength(s)

out = []
def t(x, y, s, size=14, bold=False, color=INK, anchor="start", mono=False, maxw=None):
    if maxw is not None and width(s, size, bold, mono) * 1.07 > maxw:  # 브라우저 렌더링 폭 여유 7%
        sys.exit(f"폭 초과({width(s, size, bold, mono):.0f}>{maxw}): {s}")
    fam = f' font-family="{MONO}"' if mono else ""
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}" text-anchor="{anchor}"{fam}>{html.escape(s)}</text>')
def rect(x, y, w, h, stroke=LINE, fill="none", sw=1, rx=0):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"/>')
def hline(x0, x1, y, color=LINE, sw=1): out.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{color}" stroke-width="{sw}"/>')
def arrow(x0, y0, x1, y1, color=INK, sw=1.6): out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{color}" stroke-width="{sw}" marker-end="url(#ah)"/>')

# ---- 도면과 겹층 ----
prims = []
for ln in svg_src.splitlines():
    s = ln.strip()
    if s.startswith('<path') or s.startswith('<ellipse') or s.startswith('<text'):
        prims.append(s)
def drawing(stroke, text_fill, sw=0.3):
    b = []
    for s in prims:
        if s.startswith('<text'): b.append(s.replace('font-family="Calibri"', f'font-family="Arial" fill="{text_fill}"'))
        else: b.append(s.replace('stroke="black"', f'stroke="{stroke}"').replace('stroke-width="0.25"', f'stroke-width="{sw}"'))
    return '\n'.join(b)
nodes = G['nodes']; runs = G['runs']; juncs = G['junctions']
nid = {n['id']: n for n in nodes}
ROLE_C = {'equipment': EQ, 'symbol': SYM, 'nozzle': SYM, 'instrument': INS, 'note': INS}

# H1008에서 배관으로 다른 장비를 거치지 않고 닿는 장비(질문 q003의 정답 경로)
adj = {}
for r in runs:
    if r['kind'] == 'pipe':
        adj.setdefault(r['a'], []).append((r['b'], r['id'])); adj.setdefault(r['b'], []).append((r['a'], r['id']))
start = next(n['id'] for n in nodes if n['texts'] and n['texts'][0] == 'H1008')
prev = {start: None}; q = deque([start])
while q:
    v = q.popleft()
    if v != start and v in nid and nid[v]['role'] == 'equipment': continue
    for w, rid in adj.get(v, []):
        if w not in prev: prev[w] = (v, rid); q.append(w)
targets = [k for k in prev if k in nid and nid[k]['role'] == 'equipment' and k != start]
hl_nodes, hl_runs, paths = {start}, set(), {}
for tg in targets:
    v, p = tg, []
    while v:
        p.append(v)
        if prev[v]: hl_runs.add(prev[v][1])
        v = prev[v][0] if prev[v] else None
    hl_nodes |= {x for x in p if x in nid}
    paths[nid[tg]['texts'][0]] = list(reversed(p))

def overlay():
    b = []
    for r in runs:
        pts = ' '.join(f'{x},{y}' for x, y in r['coords'])
        on = r['id'] in hl_runs
        c = ACC if on else (PIPE if r['kind'] == 'pipe' else SIG)
        dash = ' stroke-dasharray="1.2 0.8"' if r['kind'] == 'signal' else ''
        b.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="{1.6 if on else 0.8}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
    for n in nodes:
        if n['role'] not in ROLE_C: continue
        x0, y0, x1, y1 = n['bbox']
        b.append(f'<rect x="{x0-.7}" y="{y0-.7}" width="{x1-x0+1.4}" height="{y1-y0+1.4}" rx=".4" fill="none" stroke="{ROLE_C[n["role"]]}" stroke-width="{0.9 if n["id"] in hl_nodes else 0.55}"/>')
    for j in juncs:
        b.append(f'<circle cx="{j["pt"][0]}" cy="{j["pt"][1]}" r="1.2" fill="{JCT}" stroke="#fff" stroke-width=".3"/>')
    return '\n'.join(b)

VB = (168, 66, 186, 106)
def crop(x, y, w, h, body, fill="#FFFFFF"):
    rect(x, y, w, h, LINE, fill)
    out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}" preserveAspectRatio="xMidYMid meet">{body}</svg>')

# ================= 상단 =================
L, R = 56, 1544
t(L, 66, "제조·항공 기술도면의 관계 구조 복원 기반 문서 구조화", 32, True, maxw=R - L)
t(L, 104, "문제", 15, True, ACC); t(L + 46, 104, "기존 OCR은 글자와 기호는 읽지만, 선으로 이어진 연결·참조 관계는 보존하지 못함", 15, maxw=R - L - 46)
t(L, 130, "해결", 15, True, ACC); t(L + 46, 130, "원본의 선·접점·기호 관계를 복원해 좌표 기반 텍스트 구조로 변환하고, 기존 텍스트 LLM의 입력으로 활용", 15, maxw=R - L - 46)
hline(L, R, 150, INK, 1.4)
# 처리 과정 시뮬레이션 QR(https://kjhoeakjy.github.io/multimodal-doc-structuring/app/)
import re as _re
_q = open(os.path.join(HERE, 'qr-처리-과정-시뮬레이션.svg'), encoding='utf-8').read()
_d = _re.search(r' d="([^"]+)"', _q).group(1); _n = int(_re.search(r'width="(\d+)"', _q).group(1)) // 4
QS = 112
out.append(f'<svg x="{R - QS}" y="22" width="{QS}" height="{QS}" viewBox="-2 -2 {_n + 4} {_n + 4}"><rect x="-2" y="-2" width="{_n + 4}" height="{_n + 4}" fill="#FFFFFF"/><path d="{_d}" stroke="#000000" stroke-width="1" fill="none" shape-rendering="crispEdges"/></svg>')
t(R - QS - 14, 72, "처리 과정 시뮬레이션", 14, True, INK, "end")
t(R - QS - 14, 94, "문서 종류별 예시 8건 재생", 13, False, GR, "end")

# ================= 중단: 예시 3단계 =================
PW, PG = 468, 42
PX = [L, L + PW + PG, L + 2 * (PW + PG)]
TOP = 192; IH = 350
heads = ["1  원본 도면", "2  요소·연결 복원", "3  구조화 결과와 LLM 입력"]
for i, hd in enumerate(heads):
    t(PX[i], TOP - 14, hd, 18, True, ACC if i == 1 else INK, maxw=PW)
    if i < 2: arrow(PX[i] + PW + 8, TOP + IH / 2, PX[i + 1] - 8, TOP + IH / 2)

crop(PX[0], TOP, PW, IH, drawing(INK, INK))
crop(PX[1], TOP, PW, IH, drawing("#C9CDD4", "#B0B5BD") + overlay())

CAP = TOP + IH + 26
t(PX[0], CAP, "공개 P&ID 예시(DEXPI)", 14, True, maxw=PW)
t(PX[0], CAP + 22, "문자·기호·선이 함께 있는 기술도면", 14, False, GR, maxw=PW)
leg = [(EQ, "장비"), (PIPE, "배관"), (INS, "계기"), (SYM, "기호"), (SIG, "신호선"), (JCT, "접점"), (ACC, "질문 근거 경로")]
xx = PX[1]
for c, nm in leg:
    out.append(f'<rect x="{xx}" y="{CAP-11}" width="11" height="11" fill="{c}"/>'); t(xx + 15, CAP, nm, 13); xx += 15 + width(nm, 13) + 14
if xx - 14 > PX[1] + PW: sys.exit("범례 폭 초과")
t(PX[1], CAP + 22, "장비·배관·계기·기호를 분리하고, 선 끝점·접점 기준으로 연결 관계 복원", 14, False, GR, maxw=PW)

# 3: OCR 텍스트와 관계 구조 직렬화
x3 = PX[2]
ocr_lines = [l for l in CTX['ocr'].splitlines() if any(k in l for k in ("H1008", "P4712", "T4750", "PV4712"))][:3]
rect(x3, TOP, PW, 92, LINE, FILL)
t(x3 + 12, TOP + 22, "OCR 텍스트만", 13, True, GR)
for j, s in enumerate(ocr_lines):
    t(x3 + 12, TOP + 44 + j * 18, s, 12.5, False, GR, mono=True, maxw=PW - 24)
def nm(v): return nid[v]['texts'][0] if v in nid and nid[v]['texts'] else None
def path_str(p):
    named = [nm(v) for v in p if nm(v)]
    return " ─배관─ ".join(named)
b0 = nid[start]['bbox']
ser = [f"장비 H1008  좌표 ({b0[0]:.1f}, {b0[1]:.1f})–({b0[2]:.1f}, {b0[3]:.1f}) mm"]
for tg in ("T4750", "P4712"):
    if tg in paths:
        jn = sum(1 for v in paths[tg] if v not in nid)
        ser.append(path_str(paths[tg]) + (f"  (접점 {jn}곳 경유)" if jn else ""))
ser.append("배관 MNc 47126 75HB13 DN 50  선 끝점 기준 연결")
y3 = TOP + 104
rect(x3, y3, PW, IH - 104, ACC, "#FFFFFF", 1.4)
t(x3 + 12, y3 + 22, "관계 구조까지 포함한 직렬화", 13, True, ACC)
for j, s in enumerate(ser):
    t(x3 + 12, y3 + 54 + j * 31, s, 12.5, False, INK, mono=True, maxw=PW - 24)
hline(x3 + 12, x3 + PW - 12, y3 + IH - 104 - 44, LINE)
t(x3 + 12, y3 + IH - 104 - 18, "질문과 관련된 부분 그래프만 LLM에 입력(전체 직렬화 대비 길이 28%)", 13, False, GR, maxw=PW - 24)
t(x3, CAP, "질문  H1008과 배관으로 바로 연결된 장비는?", 14, True, maxw=PW)
t(x3, CAP + 22, "답  P4712, T4750  (OCR 입력 오답, 구조화 입력 정답)", 14, False, GR, maxw=PW)

# ================= 하단 =================
YB = 634
hline(L, R, YB, INK, 1.4)
t(L, YB + 34, "핵심 처리 구조", 18, True)
steps = [("01", "원본 직접 추출", "SVG·PDF의 문자·선 좌표 보존"), ("02", "스캔 보정", "OCR, 선·기호 검출, 기울기 보정"),
         ("03", "관계 복원", "문자 귀속, 선 연결, 장비 간 관계 계산"), ("04", "구조화 출력", "요소·관계·좌표를 텍스트로 직렬화")]
SW, SG = 234, 14
for k, (no, a, b) in enumerate(steps):
    sx = L + k * (SW + SG)
    rect(sx, YB + 50, SW, 92, LINE, FILL)
    t(sx + 14, YB + 82, no, 15, True, ACC, mono=True)
    t(sx + 44, YB + 82, a, 16, True, maxw=SW - 54)
    t(sx + 14, YB + 114, b, 12.5, False, GR, maxw=SW - 22)
    if k < 3: arrow(sx + SW + 1, YB + 96, sx + SW + SG - 1, YB + 96, GR, 1.2)
# 성능
PXR = L + 4 * (SW + SG) + 30
t(PXR, YB + 34, "검증", 18, True)
def stat(x, big, s1, s2, col):
    t(x, YB + 92, big, 42, True, col)
    t(x, YB + 118, s1, 14, True, maxw=R - x)
    t(x, YB + 139, s2, 13, False, GR, maxw=R - x)
stat(PXR, "27 / 27", "정답 연결 관계 복원", "공개 P&ID 벡터 도면 1건", ACC)
stat(PXR + 260, "+19.6%p", "질의응답 정답률 개선", "OCR 39.2% → 구조화 58.8%", INK)
t(L, YB + 168, "검증 조건  공개 자료 15건 240문항, 동일 소형 텍스트 LLM 비교  ·  8B 공개 모델 CPU 실행에서도 36% → 62%(80문항)", 12.5, False, GR, maxw=R - L)

# 띠
BY = 812
rect(L, BY, R - L, 46, "none", INK)
band = "제조·항공 기술문서 특화   ·   별도 VLM·GPU 없이도 적용 가능   ·   기존 텍스트 LLM 활용   ·   폐쇄망·온프레미스 운용"
t((L + R) / 2, BY + 30, band, 17, True, "#FFFFFF", "middle", maxw=R - L - 20)
t(L, BY + 70, "자료  DEXPI 참조 P&ID C01V04, FAA AC 43.13-1B, NIST 시험 도면 등 공개 자료  ·  정답 기준  DEXPI 원본 XML", 12, False, GR, maxw=R - L)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>'''
open(os.path.join(HERE, '1장-도면-관계-구조화.svg'), 'w', encoding='utf-8').write(svg)
open(os.path.join(HERE, '1장-도면-관계-구조화.html'), 'w', encoding='utf-8').write(f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">{svg}</body></html>')
print("ok", targets, {k: len(v) for k, v in paths.items()})
