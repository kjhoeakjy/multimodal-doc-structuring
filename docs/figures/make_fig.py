#!/usr/bin/env python3
"""구상안 전체 그림(가로형 1600x900) SVG 생성. v12 재구성 검증 기반 적응 표현."""
import html, sys

W, H = 1600, 900
ACC = "#1F4FD8"      # 강조색 1개(재구성 검증과 수준 상승)
INK = "#111111"; GR = "#6B6B6B"; LINE = "#B5B5B5"; FILL = "#F3F3F3"
FONT = "Pretendard, 'Noto Sans KR', sans-serif"
out = []
def t(x, y, s, size=15, w=400, color=INK, anchor="start", ls=None):
    extra = f' letter-spacing="{ls}"' if ls else ""
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{color}" text-anchor="{anchor}"{extra}>{html.escape(s)}</text>')
def lines(x, y, items, size=14, gap=22, color=INK, w=400):
    for i, s in enumerate(items):
        t(x, y + i * gap, s, size, w, color)
def hline(x0, x1, y, color=LINE, sw=1): out.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{color}" stroke-width="{sw}"/>')
def vline(x, y0, y1, color=LINE, sw=1): out.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{color}" stroke-width="{sw}"/>')
def arrow(x0, y0, x1, y1, color=INK, sw=1.2):
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{color}" stroke-width="{sw}" marker-end="url(#ah)"/>')
def rect(x, y, w, h, stroke=INK, fill="none", sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{d}/>')

# ---------- 제목 ----------
t(60, 58, "재구성 검증으로 표현 수준을 정하는 기술문서 전처리 및 구조화", 26, 600, ls="-0.5")
t(60, 86, "설계 전제: 폐쇄망 운용, 제한된 연산 자원, 독립 실행 가능한 공개 모델", 14, 400, GR)
t(1540, 86, "변환기: DocLayNet(KDD 2022), TableFormer(CVPR 2022), DePlot, Donut. 저장 단위: Dense X Retrieval(EMNLP 2024). 비교: ColPali, VisRAG(ICLR 2025)", 14, 400, GR, "end")
hline(60, 1540, 104, INK, 1.2)

# ---------- 1단: 처리 흐름 ----------
t(60, 134, "처리 흐름", 13, 600, GR, ls="1")
cols = [
    ("입력", "", ["PDF, 스캔 기술문서", "표, 그림, 도면, 각주, 주기"], ["레이아웃 모델로 영역 분할"]),
    ("1", "최저 수준 변환", ["영역마다 가능한 가장 싼 표현", "디지털: 텍스트 층, 벡터 객체", "스캔: 기본 OCR, 선과 도형 검출", "표: 격자와 셀, 차트: 표 변환"], ["CPU, 쪽당 0.2초(디지털)"]),
    ("2", "재구성 검증", ["변환 결과로 영역을 다시 그려", "원본과 비교", "미설명 잉크: 누락", "글자 불일치: 오판독, 구조 손실"], ["오류 유형 목록 없음. CPU 이미지 연산"]),
    ("3", "예산 내 수준 상승", ["검증 실패 영역을 오차 순으로", "문서당 예산 안에서 한 수준씩", "소형 문서 VLM 전사는 실패 영역에 한정", "다시 그릴 수 없는 영역은 이미지 조각"], ["GPU는 실패 영역에 한해 사용"]),
    ("4", "경로 직렬화 저장", ["값마다 레이아웃 경로를 붙인 문장", "문서, 절, 표, 머리글, 행, 셀, 각주", "도면: 표제란, 일반 주기, 개별 표기", "문서 등록 시 1회 처리 후 재사용"], ["조건 상속은 경로의 특수한 경우"]),
    ("5", "질의 시 전달", ["질문 조건과 경로가 일치하는 문장", "조건 미지정: 경로별 값 병기", "기록 없는 조건: 범위를 밝히고 보류", "이미지 조각은 필요한 질문에 한해 입력"], ["질의당 입력 토큰 최소화"]),
]
x0, y0, cw, ch, gap = 60, 150, 228, 190, 22
for i, (num, name, body, foot) in enumerate(cols):
    x = x0 + i * (cw + gap)
    rect(x, y0, cw, ch, stroke=LINE if i == 0 else INK, fill=FILL if i == 0 else "none")
    if name:
        t(x + 14, y0 + 30, num, 22, 700, ACC if num in ("2", "3") else INK)
        t(x + 40, y0 + 30, name, 17, 600)
    else:
        t(x + 14, y0 + 30, num, 17, 600)
    hline(x + 14, x + cw - 14, y0 + 42, LINE)
    lines(x + 14, y0 + 66, body, 13.5, 21)
    hline(x + 14, x + cw - 14, y0 + ch - 36, LINE)
    lines(x + 14, y0 + ch - 16, foot, 12.5, 18, GR)
    if i < len(cols) - 1:
        arrow(x + cw + 2, y0 + ch / 2, x + cw + gap - 2, y0 + ch / 2)
# 3단계에서 2단계로 되돌아가는 선(재검증)
xa = x0 + 3 * (cw + gap) + cw / 2; xb = x0 + 2 * (cw + gap) + cw / 2; yb = y0 + ch
vline(xa, yb, yb + 18, ACC, 1.2); hline(xb, xa, yb + 18, ACC, 1.2); arrow(xb, yb + 18, xb, yb + 3, ACC, 1.2)
t((xa + xb) / 2, yb + 33, "재검증", 12, 500, ACC, "middle")

# ---------- 2단: 표현 수준과 사례 ----------
Y2 = 400
t(60, Y2 + 12, "표현 수준", 13, 600, GR, ls="1")
hline(60, 1540, Y2 + 20, LINE)
lx = 60; ly = Y2 + 44
hdr = ("수준", "표현", "변환 수단", "비용", "적용 영역")
widths = (44, 150, 236, 150, 180)
rows = [("0", "텍스트 층 직접 읽기", "PDF 파서(글자, 좌표, 벡터 도형)", "CPU, 쪽당 0.2초", "디지털 PDF"),
        ("1", "OCR 텍스트", "기본 OCR, 선과 도형 검출", "CPU, 쪽당 수 초", "스캔 이미지"),
        ("2", "구조화 텍스트", "레이아웃 모델, 표 구조 모델, 차트 변환", "CPU 또는 소형 GPU", "표, 차트, 목록"),
        ("3", "소형 문서 VLM 전사", "영역 한정 전사", "GPU, 영역당 수십 초", "수준 2까지 실패한 영역"),
        ("4", "이미지 조각", "저해상도 조각을 질의 시 VLM 입력", "질의마다 시각 토큰", "다시 그릴 수 없는 영역(사진)")]
for r, row in enumerate([hdr] + rows):
    yy = ly + r * 21; xx = lx
    for c, cell in enumerate(row):
        t(xx, yy, cell, 12.5, 600 if r == 0 else 400); xx += widths[c]
    hline(lx, lx + sum(widths), yy + 7, LINE if r else INK)
t(lx, ly + 6 * 21 + 12, "아래 수준일수록 싸고 위일수록 비쌈. 검증을 통과한 가장 싼 표현을 채택함", 12, 400, GR)

# 사례
ex = 860
t(ex, Y2 + 12, "사례", 13, 600, GR, ls="1")
hdr2 = ("영역", "1차 결과", "재구성 검증", "조치")
w2 = (170, 170, 170, 170)
rows2 = [("토크 표 디지털(FAA 7-1)", "값 100개, 머리글, 각주", "통과", "수준 0 채택, 경로 직렬화"),
         ("같은 표 스캔본", "각주 줄 누락", "표 하단 미설명 잉크", "그 줄에 한해 수준 3(22초)"),
         ("도면 일반 주기(NIST)", "공차 기호 텍스트 없음", "기호 위치 미설명 잉크", "벡터 객체 해석으로 복구"),
         ("조립도 체결부 번호", "번호 1과 7 미판독", "글자 불일치", "그 원에 한해 수준 상승"),
         ("결함 사진", "텍스트 없음", "다시 그릴 수 없음", "수준 4, 질문 시 조각 입력")]
for r, row in enumerate([hdr2] + rows2):
    yy = ly + r * 21; xx = ex
    for c, cell in enumerate(row):
        t(xx, yy, cell, 12.5, 600 if r == 0 else 400, ACC if (r and c == 2 and cell != "통과" and cell != "다시 그릴 수 없음") else INK); xx += w2[c]
    hline(ex, ex + sum(w2), yy + 7, LINE if r else INK)
t(ex, ly + 6 * 21 + 12, "경로 직렬화 예: 표 7-1, 무유 카드뮴 도금 기준, 설치 권장값, 인장형 너트, 세목 계열, 1/4-28, 50~70 in-lb", 12, 400, GR)

# ---------- 3단: 검증과 한계 ----------
Y3 = 652
hline(60, 1540, Y3, LINE)
t(60, Y3 + 28, "검증", 13, 600, GR, ls="1")
t(60, Y3 + 54, "비교군", 13, 600); lines(130, Y3 + 54, ["표현 선택: 전부 최저 수준(검증 없음), 전부 최고 수준(전체 VLM 전사), 페이지 이미지 직접 입력(ColPali, VisRAG), 제안",
                                                "질의응답: 텍스트 분할 검색, Docling 검색, 페이지 전체 입력, 제안. 지표: 정답률, 조건 혼동 오답률, 보류 비율, 입력 토큰"], 13, 22)
t(60, Y3 + 110, "실측", 13, 600); lines(130, Y3 + 110, ["재구성 검증(합성 스캔 10건): 누락 131건 중 97% 탐지(의심 영역 문서당 4.4개), 오판독 166건 중 84%, 전체 오류 90% 표시",
                                                 "전처리 1쪽: 수준 0 0.2초, Docling 19초, 문서 VLM 전체 120초. 질의응답(로컬 LLM 3B): 토크 표 20/20, 도면 13/14, 비교군 2~9"], 13, 22)
vline(1010, Y3 + 14, Y3 + 150, LINE)
t(1030, Y3 + 28, "한계", 13, 600, GR, ls="1")
lines(1030, Y3 + 54, ["원본과 같은 모양으로 틀리게 읽힌 글자(기호를 글자로)는 두 신호 모두 약함",
                      "대응: 질문 시점의 근거 부재 신호, 표본 감사로 오류율 추정",
                      "사진과 도면의 기하 내용은 다시 그릴 수 없어 이미지 조각으로 남김",
                      "실측은 합성 문서와 공개 문서 2종(FAA 토크 표, NIST 도면) 기준"], 13, 22)
hline(60, 1540, Y3 + 170, INK, 1.2)
t(60, Y3 + 196, "사용 기술: 레이아웃 모델(DocLayNet 계열), 표 구조 모델(TableFormer 계열), 텍스트 층과 벡터 객체 파서, 기본 OCR, 재구성 비교(이진화, 연결 성분, 글자 대조), 소형 문서 시각언어모델(VLM), 경로 직렬화 저장, 소형 로컬 LLM", 13, 400, GR)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill="{INK}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>'''
open(sys.argv[1], "w").write(svg)
print("ok", len(svg))
