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
start = next(n['id'] for n in nodes if n['texts'] and n['texts'][0] == 'P4712')
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
t(L, 34, "AI/AX 개발  |  주제 2. 비정형 데이터 전처리 및 구조화", 14, False, GR, maxw=R - L)
t(L, 78, "제조·항공 기술문서의 시각정보 추출 및 관계 기반 구조화", 32, True, maxw=R - L)
t(L, 116, "문제", 16, True, ACC)
t(L + 48, 116, "기존 OCR은 문자를 추출하지만, 선으로 표시된 장비 간 연결관계는 텍스트에 반영하기 어려움", 16, False, INK, maxw=R - L - 48)
import re as _re
_q = open(os.path.join(HERE, 'qr-처리-과정-시뮬레이션.svg'), encoding='utf-8').read()
_d = _re.search(r' d="([^"]+)"', _q).group(1); _n = int(_re.search(r'width="(\d+)"', _q).group(1)) // 4
QS = 104
out.append(f'<svg x="{R - QS}" y="22" width="{QS}" height="{QS}" viewBox="-2 -2 {_n + 4} {_n + 4}"><rect x="-2" y="-2" width="{_n + 4}" height="{_n + 4}" fill="#FFFFFF"/><path d="{_d}" stroke="#000000" stroke-width="1" fill="none" shape-rendering="crispEdges"/></svg>')
t(R - QS - 14, 66, "처리 과정 시뮬레이션", 14, True, INK, "end")
t(R - QS - 14, 88, "문서 종류별 예시 8건 재생", 13, False, GR, "end")
hline(L, R, 138, INK, 1.4)

# ================= 중단: 실제 도면 처리 과정 =================
PWS = [440, 560, 412]; PG = 38
PX = [L, L + PWS[0] + PG, L + PWS[0] + PWS[1] + 2 * PG]
TOP = 182; IH = 352
heads = ["01  원본 도면", "02  구성요소 및 연결관계 추출", "03  관계정보 구조화 및 LLM 입력"]
for i, hd in enumerate(heads):
    t(PX[i], TOP - 14, hd, 18, True, ACC if i == 1 else INK, maxw=PWS[i])
    if i < 2: arrow(PX[i] + PWS[i] + 7, TOP + IH / 2, PX[i + 1] - 7, TOP + IH / 2)
EQ_HL = ''.join(f'<rect x="{nid[v]["bbox"][0]-1.6}" y="{nid[v]["bbox"][1]-1.6}" width="{nid[v]["bbox"][2]-nid[v]["bbox"][0]+3.2}" height="{nid[v]["bbox"][3]-nid[v]["bbox"][1]+3.2}" rx=".8" fill="none" stroke="{ACC}" stroke-width="1.1" stroke-dasharray="2 1"/>' for v in [start] + targets)
def crop2(x, y, w, h, body):
    rect(x, y, w, h, LINE, "#FFFFFF")
    out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}" preserveAspectRatio="xMidYMid meet">{body}</svg>')
crop2(PX[0], TOP, PWS[0], IH, drawing(INK, INK) + EQ_HL)
crop2(PX[1], TOP, PWS[1], IH, drawing("#C9CDD4", "#B0B5BD") + overlay())
CAP = TOP + IH + 26
t(PX[0], CAP, "공개 P&ID(배관·계장도) 벡터 도면", 14, True, maxw=PWS[0])
t(PX[0], CAP + 22, "점선 상자는 질의 예시 장비", 13.5, False, GR, maxw=PWS[0])
leg = [(EQ, "장비"), (INS, "계기"), (SYM, "밸브·기호"), (PIPE, "배관"), (SIG, "신호선"), (JCT, "분기점"), (ACC, "P4712 배관 경로")]
xx = PX[1]
for c, nm_ in leg:
    out.append(f'<rect x="{xx}" y="{CAP-11}" width="11" height="11" fill="{c}"/>'); t(xx + 15, CAP, nm_, 13); xx += 15 + width(nm_, 13) * 1.07 + 12
if xx - 12 > PX[1] + PWS[1]: sys.exit("범례 폭 초과")
t(PX[1], CAP + 22, "선의 끝점·분기점과 장비 위치를 기준으로 연결관계 판별", 13.5, False, GR, maxw=PWS[1])

# 03: OCR 텍스트와 관계 기반 구조화 비교
x3, w3 = PX[2], PWS[2]
rect(x3, TOP, w3, 82, LINE, FILL)
t(x3 + 12, TOP + 22, "OCR 텍스트", 13, True, GR)
t(x3 + 12, TOP + 46, "T4750, P4712, H1008, TICSA 4750.03 …", 13, False, GR, mono=True, maxw=w3 - 24)
t(x3 + 12, TOP + 69, "문자 목록, 장비 간 관계 확인 불가", 12.5, False, GR, maxw=w3 - 24)
y3 = TOP + 94; GH = 158
rect(x3, y3, w3, GH, ACC, "#FFFFFF", 1.4)
t(x3 + 12, y3 + 22, "관계 기반 구조화", 13, True, ACC)
def node(cx, cy, label, col):
    wv = width(label, 14, True, True) + 24
    rect(cx - wv / 2, cy - 15, wv, 30, col, "#FFFFFF", 1.6, 3)
    t(cx, cy + 5, label, 14, True, col, "middle", mono=True)
    return wv
ax, ay = x3 + 80, y3 + 84
tg_names = sorted(nid[v]['texts'][0] for v in targets)
for k, nm_ in enumerate(tg_names):
    by_ = y3 + 56 + k * 56; bx = x3 + w3 - 78
    arrow(ax + 46, ay, bx - 50, by_, ACC, 1.6)
    t((ax + bx) / 2 + 6, (ay + by_) / 2 + (-12 if k == 0 else 22), "배관 경로", 12, False, ACC, "middle")
    node(bx, by_, nm_, EQ)
node(ax, ay, "P4712", EQ)
t(x3 + 12, y3 + GH - 12, "장비·연결관계·원본 좌표를 함께 저장", 12.5, False, GR, maxw=w3 - 24)
yq = y3 + GH + 12
QH = IH - (yq - TOP)
rect(x3, yq, w3, QH, "none", FILL)
t(x3 + 12, yq + QH / 2 - 6, "Q.", 14, True, GR); t(x3 + 40, yq + QH / 2 - 6, "P4712와 배관 경로로 연결되는 장비는?", 14, True, INK, maxw=w3 - 52)
t(x3 + 12, yq + QH / 2 + 22, "A.", 14, True, GR); t(x3 + 40, yq + QH / 2 + 22, ", ".join(tg_names), 14, True, ACC, maxw=w3 - 52)
t(x3, CAP, "기존 텍스트 LLM 입력으로 사용", 14, True, maxw=w3)
t(x3, CAP + 22, "질문 관련 연결정보로 입력 한정, 전체의 약 28% 분량", 13.5, False, GR, maxw=w3)

# ================= 하단: 기술적 차별점(왼쪽 절반)과 성능(오른쪽 절반) =================
# 성능 근거: examples/public-documents/README.md(도면별 정답 인접 쌍), examples/llm-qa/README.md(래스터·스캔 개선값),
# examples/llm-qa/results/open-8b-2026-10-s80.jsonl(공개 가중치 8B, CPU, 80문항)
recall = [27/27, 19/26, 17/24, 3/6, 4/9]   # C01 원본·200 dpi·스캔, C02·C03 원본. examples/public-documents/pid/output/current 재평가 값
import json as _json
_rows = [_json.loads(l) for l in open(os.path.join(ROOT, 'examples/llm-qa/results/open-8b-2026-10-s80.jsonl'), encoding='utf-8') if l.strip()]
def _acc(cond):
    r = [x for x in _rows if x['cond'] == cond]; return 100 * sum(1 for x in r if x['correct']) / len(r), len(r)
qa_ocr, nq = _acc('ocr'); qa_full, _ = _acc('full')
from decimal import Decimal, ROUND_HALF_UP
f1 = lambda v: str(Decimal(str(v)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
YB = TOP + IH + 70
hline(L, R, YB, INK, 1.4)
MID = (L + R) / 2
out.append(f'<line x1="{MID}" y1="{YB+16}" x2="{MID}" y2="{YB+182}" stroke="{LINE}" stroke-width="1"/>')
t(L, YB + 32, "기술적 차별점", 16, True)
cards = [("문자뿐 아니라 연결관계까지 구조화", ["선의 끝점과 분기점을 분석해 장비·계기 간 연결관계를 추출"]),
         ("벡터 원본 우선 활용 · CPU 기반 전처리", ["PDF·SVG의 선과 문자 좌표를 직접 추출하고 스캔본에는 OCR·영상처리 적용", "별도 생성형 VLM이나 GPU 없이 도면 전처리 가능"])]
CWD = MID - L - 28
cy = YB + 44
for k, (tt, lines) in enumerate(cards):
    hh = 34 + 22 * len(lines)
    rect(L, cy, CWD, hh, LINE, FILL)
    out.append(f'<rect x="{L}" y="{cy}" width="4" height="{hh}" fill="{ACC}"/>')
    t(L + 18, cy + 24, tt, 15.5, True, maxw=CWD - 32)
    for j, ln in enumerate(lines):
        t(L + 18, cy + 47 + j * 22, ln, 13.5, False, GR, maxw=CWD - 32)
    cy += hh + 8
SXL = MID + 28
t(SXL, YB + 32, "성능", 16, True)
mets = [(f"{100*sum(recall)/len(recall):.1f}%", "배관 연결 재현율", ["공개 P&ID 5개 입력 조건 평균", "(원본 3건, 200 dpi·스캔 변환)"], INK),
        ("20/21", "삽화–표 행 대응", ["FAA 정비 문서 볼트 표", "21개 행 육안 대조"], INK),
        (f"+{f1(qa_full-qa_ocr)}%p", "LLM 정답률 개선", [f"OCR {f1(qa_ocr)}%, 관계 구조화 {f1(qa_full)}%", f"공개 가중치 8B · CPU · 동일 {nq}문항"], ACC)]
GW = (R - SXL) / 3
for k, (big, s1, s2, col) in enumerate(mets):
    gx = SXL + k * GW
    t(gx, YB + 80, big, 30, True, col, maxw=GW - 14)
    t(gx, YB + 106, s1, 14, True, maxw=GW - 14)
    for j, ln in enumerate(s2):
        t(gx, YB + 128 + j * 19, ln, 12.5, False, GR, maxw=GW - 14)
t(SXL, YB + 184, "평가 자료  공개 P&ID, FAA 정비 문서, 합성 기술문서(동일 원본의 입력 형식 변형 포함)", 12, False, GR, maxw=R - SXL)

BY = YB + 200
rect(L, BY, R - L, 42, "none", INK)
band = "기존 PDF·SVG 활용   ·   CPU 기반 도면 전처리   ·   기존 텍스트 LLM 연계   ·   폐쇄망 적용 가능한 구성"
t((L + R) / 2, BY + 28, band, 17, True, "#FFFFFF", "middle", maxw=R - L - 20)
t(L, BY + 64, "예시 도면  공정 설계 데이터 교환 표준(DEXPI)의 공개 P&ID  ·  연결 정답은 원본 설계 파일 기준", 12, False, GR, maxw=R - L)
if BY + 64 > H - 8: sys.exit(f"세로 초과 {BY + 64}")

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>"""
open(os.path.join(HERE, '1장-도면-관계-구조화.svg'), 'w', encoding='utf-8').write(svg)
open(os.path.join(HERE, '1장-도면-관계-구조화.html'), 'w', encoding='utf-8').write(f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">{svg}</body></html>')
print("ok", BY + 64, tg_names, round(100*sum(recall)/len(recall),2), round(qa_ocr,1), round(qa_full,1), nq)
