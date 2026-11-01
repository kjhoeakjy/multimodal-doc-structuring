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
ACC = "#1F4FD8"; ORG = "#D9480F"; GRN = "#15803D"; INK = "#111111"; GR = "#3A3D42"; LINE = "#CFD3D9"; FILL = "#F3F4F6"
EQ, SYM, INS, PIPE, SIG, JCT, TBL = "#C8322E", "#1F4FD8", "#7A2BD1", "#1E8E57", "#2F80ED", "#E0A400", "#E8710A"
FONT = "'Wanted Sans', sans-serif"; MONO = "Consolas, 'Wanted Sans', monospace"
WS = {False: os.path.join(HERE, 'fonts', 'WantedSans-Medium.ttf'), True: os.path.join(HERE, 'fonts', 'WantedSans-Bold.ttf')}   # Wanted Sans, SIL OFL 1.1
FD = "C:/Windows/Fonts/"
_f = {}
def fnt(size, bold=False, mono=False):
    k = (size, bold, mono)
    if k not in _f:
        _f[k] = ImageFont.truetype(FD + "consola.ttf" if mono else WS[bold], size)
    return _f[k]
def width(s, size, bold=False, mono=False):
    if mono:  # 고정폭 글꼴에 한글이 섞이면 한글은 대체 글꼴 폭으로 계산
        return sum(fnt(size, False, True).getlength(c) if ord(c) < 0x1100 else fnt(size).getlength(c) for c in s)
    return fnt(size, bold).getlength(s)

out = []
def t(x, y, s, size=14, bold=False, color=INK, anchor="start", mono=False, maxw=None):
    if not mono:
        import re as _r0; s = _r0.sub(r"\s*·\s*", ", ", s)   # 낱말 사이 가운뎃점은 쉼표로
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
    for tb in G['tables']:
        x0, y0, x1, y1 = tb['bbox']; on = 'H1008' in tb['rows'][0]
        b.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" fill="{TBL}" fill-opacity=".10" stroke="{ACC if on else TBL}" stroke-width="{1.4 if on else 0.8}"/>')
    for j in juncs:
        b.append(f'<circle cx="{j["pt"][0]}" cy="{j["pt"][1]}" r="1.2" fill="{JCT}" stroke="#fff" stroke-width=".3"/>')
    return '\n'.join(b)

VB = (64, 54, 328, 152)
def crop(x, y, w, h, body, fill="#FFFFFF"):
    rect(x, y, w, h, LINE, fill)
    out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}" preserveAspectRatio="xMidYMid meet">{body}</svg>')

# ================= 상단 =================
L, R = 80, 1520; TY = 34   # 바깥 여백
t(L, 30 + TY, "AI/AX 개발  |  주제 2. 비정형 데이터 전처리 및 구조화", 12.5, False, GR, maxw=R - L)
t(L, 68 + TY, "제조·항공 기술문서의 시각정보 추출 및 관계 기반 구조화", 28, True, maxw=R - L)
t(L, 101 + TY, "문제", 14, True, ACC)
t(L + 42, 101 + TY, "기존 OCR 인식 등의 비정형 데이터 전처리 방식은 복잡한 도면에 존재하는 다양한 연결관계를 반영하지 못함", 14, False, INK, maxw=R - L - 42)
import re as _re
_q = open(os.path.join(HERE, 'qr-처리-과정-시뮬레이션.svg'), encoding='utf-8').read()
_d = _re.search(r' d="([^"]+)"', _q).group(1); _n = int(_re.search(r'width="(\d+)"', _q).group(1)) // 4
QS = 92
out.append(f'<svg x="{R - QS}" y="{18 + TY}" width="{QS}" height="{QS}" viewBox="-2 -2 {_n + 4} {_n + 4}"><rect x="-2" y="-2" width="{_n + 4}" height="{_n + 4}" fill="#FFFFFF"/><path d="{_d}" stroke="#000000" stroke-width="1" fill="none" shape-rendering="crispEdges"/></svg>')
t(R - QS - 12, 60 + TY, "데이터 처리 과정 시뮬레이터", 12.5, True, INK, "end")
t(R - QS - 12, 79 + TY, "문서 유형별 예시 8건", 11.5, False, GR, "end")
hline(L, R, 120 + TY, INK, 1.4)

# ================= 중단: 원본 도면과 추출 결과 =================
PWS = [708, 708]; PG = 24
PX = [L, L + PWS[0] + PG]
TOP = 196; IH = 328
heads = ["01  원본 도면", "02  구성요소 및 연결관계 추출"]
for i, hd in enumerate(heads):
    t(PX[i], TOP - 12, hd, 15.5, True, INK, maxw=PWS[i])
arrow(PX[0] + PWS[0] + 5, TOP + IH / 2, PX[1] - 5, TOP + IH / 2)
EQ_HL = ''.join(f'<rect x="{nid[v]["bbox"][0]-1.6}" y="{nid[v]["bbox"][1]-1.6}" width="{nid[v]["bbox"][2]-nid[v]["bbox"][0]+3.2}" height="{nid[v]["bbox"][3]-nid[v]["bbox"][1]+3.2}" rx=".8" fill="none" stroke="{ACC}" stroke-width="1.1" stroke-dasharray="2 1"/>' for v in [start] + targets)
def crop2(x, y, w, h, body):
    rect(x, y, w, h, LINE, "#FFFFFF")
    out.append(f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="{VB[0]} {VB[1]} {VB[2]} {VB[3]}" preserveAspectRatio="xMidYMid meet">{body}</svg>')
crop2(PX[0], TOP, PWS[0], IH, drawing(INK, INK) + EQ_HL)
crop2(PX[1], TOP, PWS[1], IH, drawing("#C9CDD4", "#B0B5BD") + overlay())
CAP = TOP + IH + 22
t(PX[0], CAP, "공개 P&ID(배관계장도) 벡터 도면", 12.5, True, maxw=PWS[0])
t(PX[0], CAP + 19, "장비 5, 계기 4, 밸브 및 기호 19, 배관 구간 37, 신호선 7  ·  점선: 질의 대상 장비", 12, False, GR, maxw=PWS[0])
leg = [(EQ, "장비"), (INS, "계기"), (SYM, "밸브 및 기호"), (PIPE, "배관"), (SIG, "신호선"), (JCT, "접속점"), (ACC, "H1008 배관 경로")]
xx = PX[1]
for c, nm_ in leg:
    out.append(f'<rect x="{xx}" y="{CAP-10}" width="10" height="10" fill="{c}"/>'); t(xx + 14, CAP, nm_, 12); xx += 14 + width(nm_, 12) * 1.07 + 12
if xx - 12 > PX[1] + PWS[1]: sys.exit("범례 폭 초과")
t(PX[1], CAP + 19, "연결선 끝점과 접속점, 장비 위치 기준의 연결관계 판별", 12, False, GR, maxw=PWS[1])

def fit(s, size, maxw):  # 실제 텍스트를 칸 폭에 맞춰 뒤쪽을 줄임표로 생략
    if width(s, size, mono=True) * 1.07 <= maxw: return s
    while width(s + ' …', size, mono=True) * 1.07 > maxw: s = s[:-1]
    return s.rstrip() + ' …'

# ================= 하단: 03 관계정보 구조화, 04 LLM 응답 테스트, 05 성능 =================
# 성능 근거: examples/public-documents/README.md(도면별 정답 인접 쌍), examples/llm-qa/README.md,
# examples/llm-qa/results/open-8b-2026-10-all.jsonl(공개 가중치 8B, CPU, 공개·합성 문서 15건, 240문항 전체)
label = [60/62, 32/40, 28/31, 36/61, 4/4]; label_n = 62 + 40 + 31 + 61 + 4   # 문자 태그가 맞는 도면 요소에 붙은 비율, 같은 재평가 결과
recall = [27/27, 19/26, 17/24, 3/6, 4/9, 82/157, 10/25]   # C01 원본·200 dpi·스캔, C02·C03·증류 플랜트·증류 실험실 원본. examples/public-documents/pid/output/current 재평가 값
n_pairs = 27 + 26 + 24 + 6 + 9 + 157 + 25
import json as _json
_rows = [_json.loads(l) for l in open(os.path.join(ROOT, 'examples/llm-qa/results/open-8b-2026-10-all.jsonl'), encoding='utf-8') if l.strip()]
def _acc(cond):
    r = [x for x in _rows if x['cond'] == cond]; return 100 * sum(1 for x in r if x['correct']) / len(r), len(r)
qa_ocr, nq = _acc('ocr'); qa_full, _ = _acc('full')
ndoc = len({x['doc'] for x in _rows})
from decimal import Decimal, ROUND_HALF_UP
f1 = lambda v: str(Decimal(str(v)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))
NQ = json.load(open(os.path.join(ROOT, 'examples/llm-qa/results/slide-natural-question.json'), encoding='utf-8'))   # llama3.1:8b, CPU, temperature 0
ans = {r['cond']: r for r in NQ}

YB = CAP + 34
CW = (R - L - 2 * 20) / 3; CH = 186
CX = [L + i * (CW + 20) for i in range(3)]
CARD = "#F4F5F7"
for i in range(3):
    rect(CX[i], YB, CW, CH, "#D5D8DD", CARD, 1)
def head(i, txt, note):
    t(CX[i] + 18, YB + 28, txt, 15, True)
    if note:
        hw = width(txt, 15, True) * 1.07 + 10
        t(CX[i] + CW - 18, YB + 28, note, 11, False, GR, "end", maxw=CW - 36 - hw)
IX = [x + 18 for x in CX]; IW = CW - 36; IY = YB + 42

# 03 관계정보 구조화: OCR 결과와 구조화 텍스트(전체 직렬화 텍스트 일부, 성능 수치와 같은 입력 조건)
head(0, "03  관계정보 구조화", "장비·연결관계·표를 단일 텍스트로 변환")
ol = CTX['ocr'].splitlines(); oi = next(i for i, l in enumerate(ol) if 'H1008' in l)
OH = 40
rect(IX[0], IY, IW, OH, ORG, "#FFFFFF", 1.2)
t(IX[0] + 10, IY + 15, "OCR 전처리 결과", 11, True, ORG)
NA, NB = "장비 간 연결관계 미반영", "장비, 연결관계, 원본 좌표 저장"
OCRL = fit('  '.join(ol[oi:oi + 3]), 10, IW - 20)
XC = IX[0] + 10 + width(OCRL, 10, mono=True) * 1.07 / 2   # 두 설명과 화살표를 칸 안 글자 덩어리의 가운데에 맞춤
t(XC, IY + 15, NA, 11, True, ACC, "middle")
t(IX[0] + 10, IY + 31, OCRL, 10, False, GR, mono=True)
y3 = IY + OH + 22; GH = YB + CH - 14 - y3
arrow(XC, IY + OH + 4, XC, y3 - 8, ACC, 1.6)
rect(IX[0], y3, IW, GH, GRN, "#FFFFFF", 1.4)
t(IX[0] + 10, y3 + 15, "구조화 텍스트", 11, True, GRN)
t(XC, y3 + 15, NB, 11, True, ACC, "middle")
rl = CTX['full'].splitlines()
pick = [next(l for l in rl if l.startswith(p)) for p in ("n19 종류=equipment", "r30 종류=pipe", "H1008 →")]
for k, ln in enumerate(pick):
    em = ln.startswith('H1008 →')
    t(IX[0] + 10, y3 + 31 + k * 15, fit(ln, 10, IW - 20), 10, em, INK if em else "#333333", mono=True)
if 31 + 2 * 15 > GH - 4: sys.exit(f"03 칸 높이 초과 {GH}")

# 04 LLM 응답 테스트: 같은 질문에 입력 자료만 바꾼 실제 응답. 구분 표시만 색, 답변 내용은 검정
head(1, "04  LLM 응답 테스트", "Llama 3.1 8B, CPU 사용")
rows = [("질문", GR, ans['full']['question']),
        ("구조화 입력 답변 · 정답", GRN, ans['full']['response']),
        ("OCR 입력 답변 · 오답", ORG, ans['ocr']['response'])]
for k, (lab, lc, txt) in enumerate(rows):
    yy = IY + 14 + k * 46
    t(IX[1], yy, lab, 11, True, lc)
    t(IX[1], yy + 18, txt, 13, True, INK, maxw=IW)
    if k < 2: out.append(f'<line x1="{IX[1]}" y1="{yy + 30}" x2="{IX[1] + IW}" y2="{yy + 30}" stroke="#D5D8DD" stroke-width="1"/>')

# 05 성능: 지표를 세로로 나열
head(2, "05  성능", "공개·합성 자료 기준 실측")
mets = [(f"{100*sum(recall)/len(recall):.1f}%", "배관 연결 재현율", f"공개 P&ID 5장 원본과 변환본, 정답 연결 {n_pairs}쌍", INK),
        (f"{100*sum(label)/len(label):.1f}%", "기호와 명칭 대응 정확도", "", INK),
        (f"+{f1(qa_full-qa_ocr)}%p", "LLM 정답률 개선", f"OCR {f1(qa_ocr)}%, 관계 구조화 {f1(qa_full)}%, 문서 {ndoc}건 {nq}문항 평균", ACC)]
NX = R - 6 - width(mets[2][0], 24, True) * 1.07   # 가장 긴 숫자의 끝을 위 도면 칸 오른쪽 끝에 맞추고 세 숫자는 왼쪽 정렬
for k, (big, s1, s2, col) in enumerate(mets):
    yy = IY + k * 46
    if s2:
        t(IX[2], yy + 13, s1, 12.5, True, maxw=NX - IX[2] - 10)
        t(IX[2], yy + 30, s2, 11, False, GR, maxw=NX - IX[2] - 10)
    else:
        t(IX[2], yy + 22, s1, 12.5, True, maxw=NX - IX[2] - 10)
    t(NX, yy + 27, big, 24, True, col)
    if k < 2: out.append(f'<line x1="{IX[2]}" y1="{yy + 42}" x2="{IX[2] + IW}" y2="{yy + 42}" stroke="#D5D8DD" stroke-width="1"/>')

BY = YB + CH + 14
DRED = "#9B1C1C"   # 진한 빨강
rect(L, BY, R - L, 46, "none", "#FBF3F3")
hline(L, R, BY, DRED, 1.6); hline(L, R, BY + 46, DRED, 1.6)
band = ["PDF, SVG 원본 직접 활용", "CPU 사용", "VLM, GPU 사용 없이 비정형 데이터 처리", "외부 서버 전송 없는 로컬 실행"]   # 네 항목을 같은 간격의 공백으로 구분
bw = [width(b, 18, True) * 1.07 for b in band]; gap = (R - L - 80 - sum(bw)) / (len(band) - 1)
bx = L + 40
for b, w_ in zip(band, bw):
    t(bx, BY + 30, b, 18, True, DRED); bx += w_ + gap
t(L, BY + 66, "예시 도면  공정 설계 데이터 교환 표준(DEXPI)의 공개 P&ID", 11, False, GR, maxw=R - L)
if BY + 66 > H - 8: sys.exit(f"세로 초과 {BY + 66}")

def font_css():  # 슬라이드에 쓰인 글자만 남긴 글꼴을 SVG 안에 넣어 PDF·PNG 어디서나 같은 글꼴로 보이게 함
    import base64, io, re as _r
    from fontTools import subset
    chars = set(html.unescape(''.join(_r.findall(r'>([^<]*)</text>', ' '.join(out))))) | set('0123456789')
    css = []
    for bold, w in ((False, 400), (True, 700)):
        f = subset.load_font(WS[bold], subset.Options()); o = subset.Options(); o.flavor = 'woff'
        sb = subset.Subsetter(o); sb.populate(text=''.join(chars)); sb.subset(f)
        b = io.BytesIO(); subset.save_font(f, b, o)
        css.append(f"@font-face{{font-family:'Wanted Sans';font-weight:{w};src:url(data:font/woff;base64,{base64.b64encode(b.getvalue()).decode()}) format('woff')}}")
    return '<style>' + ''.join(css) + '</style>'

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs>{font_css()}<marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>"""
open(os.path.join(HERE, '1장-도면-관계-구조화.svg'), 'w', encoding='utf-8').write(svg)
open(os.path.join(HERE, '1장-도면-관계-구조화.html'), 'w', encoding='utf-8').write(f'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0">{svg}</body></html>')
print("ok", BY + 66, [nid[v]["texts"][0] for v in targets], round(100*sum(recall)/len(recall),2), round(qa_ocr,1), round(qa_full,1), nq)
