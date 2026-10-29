#!/usr/bin/env python3
"""파이프라인 전체 그림(가로형 1600x1000) SVG 생성. 실행: python3 make_pipeline_fig.py > 파이프라인-전체-그림.svg"""
import html

W, H = 1600, 1000
ACC = "#1F4FD8"
INK = "#111111"; GR = "#6B6B6B"; LINE = "#B5B5B5"; FILL = "#F4F4F4"
FONT = "Pretendard, 'Noto Sans KR', sans-serif"
out = []

def t(x, y, s, size=14, w=400, color=INK, anchor="start", ls=None, mono=False):
    extra = f' letter-spacing="{ls}"' if ls else ""
    fam = ' font-family="JetBrains Mono, DejaVu Sans Mono, monospace"' if mono else ""
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{color}" text-anchor="{anchor}"{extra}{fam}>{html.escape(s)}</text>')

def lines(x, y, items, size=13, gap=20, color=INK, w=400, mono=False):
    for i, s in enumerate(items):
        if s.startswith("#"):
            t(x, y + i * gap, s[1:], size, 600, GR, mono=mono)
        else:
            t(x, y + i * gap, s, size, w, color, mono=mono)

def hline(x0, x1, y, color=LINE, sw=1):
    out.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{color}" stroke-width="{sw}"/>')

def vline(x, y0, y1, color=LINE, sw=1):
    out.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{color}" stroke-width="{sw}"/>')

def arrow(x0, y0, x1, y1, color=INK, sw=1.2):
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{color}" stroke-width="{sw}" marker-end="url(#ah)"/>')

def rect(x, y, w, h, stroke=INK, fill="none", sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" stroke="{stroke}" fill="{fill}" stroke-width="{sw}"{d}/>')

# ---------- 제목 ----------
t(60, 56, "기술 그림의 관계 그래프 기반 구조화 및 LLM 연계: 처리 흐름", 26, 600, ls="-0.5")
t(60, 84, "전제: 폐쇄망, CPU 또는 제한된 GPU, 생성형 VLM 미사용, 기존 텍스트 LLM. 모델은 문자 인식과 임베딩 두 곳에만 쓰고 관계 복원은 기하 규칙으로 수행", 14, 400, GR)
hline(60, 1540, 102, INK, 1.2)

# ---------- 1단: 처리 흐름 ----------
t(60, 130, "처리 흐름", 13, 600, GR, ls="1")
cols = [
    ("입력", "", [
        "#벡터 원본",
        "PDF 경로·문자, CAD(DXF·SVG),",
        "P&ID 교환 형식(Proteus XML)",
        "#래스터",
        "스캔 PNG·JPEG·TIFF, 100~300 dpi",
        "#전처리",
        "쪽 안의 그림·표·본문 영역 분할",
        "기울기 보정(긴 선 각도 중앙값)",
        "잡음 제거(중앙값 필터)",
    ], ["벡터 원본이 있으면 이미지로 바꾸지 않음"]),
    ("1", "시각 요소 추출", [
        "#벡터 경로",
        "경로를 직선·곡선·타원·문자로 분해",
        "변환 행렬 적용, 선 굵기·점선 보존",
        "색·식별자·그룹 이름은 사용 안 함",
        "#래스터 경로",
        "OCR(CPU 문자 인식 모델) 후 문자 지움",
        "형태학 열림으로 축 평행 선과 굵기",
        "구멍 윤곽으로 닫힌 도형",
        "잔여 잉크 덩어리를 기호·표식으로",
    ], ["모델 사용 지점 1: 문자 인식"]),
    ("2", "관계 그래프 생성", [
        "#노드",
        "닫힌 도형(장비), 기호 묶음, 계기,",
        "문자, 접속구, 화살표, 표",
        "#간선",
        "접속: 선 끝이 0.6 mm 안에서 닿음",
        "간격 후보: 선 방향 5 mm 또는 굵기 10배",
        "분기점, 포함, 지시(화살표 꼭짓점),",
        "라벨(4 mm 안 문자, 선 번호 형식)",
        "선 종류: 점선·상대 굵기로 배관·신호선",
    ], ["연결은 선·접점 분석으로만 확정. 근접은 후보"]),
    ("3", "근거 연결과 검색", [
        "#근거",
        "모든 노드·간선에 원본 좌표(mm) 보존",
        "표는 행·칸 단위, 그림 영역은 행과 묶음",
        "#직렬화",
        "노드 목록·구간 목록의 텍스트",
        "#색인",
        "그래프 텍스트 BM25, 태그·도면 번호",
        "완전 일치, 쪽·그림 이미지 임베딩",
        "질문의 시작 노드에서 k단계 부분 그래프",
    ], ["모델 사용 지점 2: 경량 이미지 임베딩"]),
    ("4", "기존 텍스트 LLM", [
        "#입력",
        "부분 그래프 텍스트, 확정 해석,",
        "미해석 목록. 이미지는 넣지 않음",
        "#출력",
        "답변과 근거 노드·구간의 좌표",
        "원본 그림 위에 근거 영역 표시",
        "#근거",
        "관계가 명시된 표현에서 텍스트 LLM의",
        "그림 질의 정확도 상승(VGBench 2024)",
    ], ["전처리는 등록 시 1회, 질의 시 부분 그래프만"]),
]
x0, y0, cw, ch, gap = 60, 146, 272, 268, 30
for i, (num, name, body, foot) in enumerate(cols):
    x = x0 + i * (cw + gap)
    rect(x, y0, cw, ch, stroke=LINE if i == 0 else INK, fill=FILL if i == 0 else "none")
    if name:
        t(x + 14, y0 + 30, num, 22, 700, ACC if num == "2" else INK)
        t(x + 40, y0 + 30, name, 17, 600)
    else:
        t(x + 14, y0 + 30, num, 17, 600)
    hline(x + 14, x + cw - 14, y0 + 42, LINE)
    lines(x + 14, y0 + 64, body, 12.5, 20)
    hline(x + 14, x + cw - 14, y0 + ch - 34, LINE)
    lines(x + 14, y0 + ch - 14, foot, 12, 17, GR)
    if i < len(cols) - 1:
        arrow(x + cw + 3, y0 + ch / 2, x + cw + gap - 3, y0 + ch / 2)

# ---------- 2단: 직렬화 예, 판정 규칙, 모델과 연산 ----------
y1 = 446
t(60, y1, "직렬화 예(공개 참조 P&ID, 질문 \"P4712 펌프의 토출 측 연결\")", 13, 600, GR, ls="1")
rect(60, y1 + 12, 610, 150, LINE, FILL)
lines(74, y1 + 36, [
    "n25 종류=equipment 이름=P4712 라벨=P4712|N1|50|N2|50 bbox=(245.8,148.8,256.2,159.2)",
    "r9  종류=pipe A=n25[equipment P4712] B=j2 경로=(256.2,154.0)→(265.0,154.0)",
    "j2  --r11--> n7[symbol 73KH12-25]  근거 pt=(265.0,154.0) bbox=(264.0,158.0,266.0,162.0)",
    "j0  --r13(MNc 47125 73HG12 25)--> n4[symbol SV 104.01]  근거 bbox=(267.0,89.0,270.0,96.0)",
    "r23 종류=signal A=n17[instrument TICSA] B=n13[symbol TV4750.03] 간격=4.05mm(후보)",
    "",
    "OCR 결과는 P4712, 73KH12-25, SV 104.01이 같은 그림에 있다는 사실까지 전달됨",
], 10.5, 19, mono=True)

t(700, y1, "판정 규칙(A3 도면 축척 기준, 다른 축척은 비례 조정)", 13, 600, GR, ls="1")
rules = [
    ("선 후보", "축 평행 직선 6 mm 이상. 같은 축에서 병합, 기호에서 절단"),
    ("접속", "끝점 거리 0.6 mm. 다른 선 끝이 닿는 곳은 분기점"),
    ("간격 후보", "선 방향 5 mm 또는 지배적 선 굵기의 10배 안의 요소"),
    ("틀·표", "쪽 80% 이상 덮는 사각형은 틀. 격자가 경계 90% 덮고 문자 6개 이상이면 표"),
    ("빈 칸 제외", "직선으로 둘러싸이고 3 mm 넘는 내부 선이 없는 구멍은 장비가 아님"),
    ("신호선", "점선이거나 굵은 선 부류의 절반(래스터 0.35) 미만 굵기"),
    ("라벨", "요소 상자 안 또는 4 mm 안 문자. 선 번호 형식은 평행한 선의 라벨"),
]
yy = y1 + 34
for k, v in rules:
    t(700, yy, k, 12.5, 600)
    t(790, yy, v, 12.5)
    yy += 19
hline(700, 1200, yy - 6, LINE)
t(700, yy + 12, "역할 추정: 장비 태그 형식(영문 1자+숫자 4자리), 계기 기능 문자와 루프 번호. 기호 종류 분류는 후속(소형 분류기)", 12, 400, GR)

t(1230, y1, "모델과 연산", 13, 600, GR, ls="1")
models = [
    ("문자 인식", "공개 OCR 모델 1종, CPU", "A3 200 dpi 40초/쪽"),
    ("선·기호·표", "영상 처리 규칙, CPU", "7~19초/쪽"),
    ("그래프", "기하 규칙, CPU", "1~13초/쪽"),
    ("벡터 경로", "모델 없음, CPU", "0.7~10.6초/장"),
    ("이미지 임베딩", "경량 멀티모달 임베딩", "등록 시 1회"),
    ("질의응답", "기존 텍스트 LLM", "부분 그래프 텍스트만"),
]
yy = y1 + 34
for a, b, c in models:
    t(1230, yy, a, 12.5, 600); t(1318, yy, b, 12.5); t(1460, yy, c, 12.5, 400, GR)
    yy += 19
hline(1230, 1540, yy - 6, LINE)
t(1230, yy + 12, "GPU는 임베딩과 LLM에 한정. 생성형 VLM 없음", 12, 400, GR)

# ---------- 3단: 실측 결과와 한계 ----------
y2 = 650
t(60, y2, "실측 결과(공개 자료, 2026-10-29)", 13, 600, GR, ls="1")
hdr = ["자료", "조건", "정답 쌍 복원", "라벨 소속", "비고"]
rows = [
    ("DEXPI 참조 P&ID C01", "벡터", "27/27", "60/62", "표준 기호 도면. 오류 쌍 0"),
    ("같은 도면", "래스터 200 dpi", "14/26", "15/40", "선 굵기 1픽셀 오차, 문자 자리 끊김"),
    ("같은 도면", "스캔 열화", "10/23", "7/25", "0.4도 회전·잡음·JPEG. 보정 후"),
    ("DEXPI C02·C03", "벡터", "3/6, 4/9", "35/61, 4/4", "컬럼 몸체 변이 배관으로 분류"),
    ("증류 플랜트(157쌍)", "벡터", "84/157", "문자 없음", "작성 도구가 배관 끝을 5 mm 띄움"),
    ("FAA 볼트 표 21행", "래스터 100 dpi", "삽화·행 묶음 20/21", "부품 번호 17/21", "O/0, 1/O 혼동"),
    ("NIST 치수 도면", "래스터 200 dpi", "지시선 1/10", "-", "회전 주기, 윤곽선과 혼동"),
]
cx = [60, 250, 400, 560, 700]
yy = y2 + 26
for j, h_ in enumerate(hdr):
    t(cx[j], yy, h_, 12, 600, GR)
hline(60, 1000, yy + 8, LINE)
yy += 28
for r in rows:
    for j, v in enumerate(r):
        t(cx[j], yy, v, 12.5, 600 if j == 2 else 400, ACC if j == 2 and r[1] == "벡터" and v.startswith("27") else INK)
    yy += 21
hline(60, 1000, yy - 12, LINE)

t(1040, y2, "설계 원칙과 한계", 13, 600, GR, ls="1")
lines(1040, y2 + 26, [
    "#원칙",
    "벡터 원본 우선. 래스터는 검토 인력을 둔 보조 경로",
    "관계는 선·접점 분석으로 확정하고 근접은 후보로만 기록",
    "임계값은 도면의 선 굵기·축척에 상대적으로 정함",
    "답변마다 근거 좌표를 붙여 원본에서 확인 가능하게 함",
    "#한계",
    "기호 종류 분류 없음. 큰 장비가 주변 부품을 흡수",
    "래스터에서 0.2 mm와 0.25 mm 선 구분 불가",
    "등각 투상도의 회전 문자와 지시선은 벡터 경로 필요",
    "정답 있는 자료는 P&ID 5장. 정비 문서는 표본 육안 대조",
], 12.5, 20)

hline(60, 1540, 968, LINE)
t(60, 988, "공개 자료: DEXPI 참조 P&ID와 Proteus XML, FAA AC 43.13-1B, NIST PMI 시험 모형. 실측은 CPU 4코어 컨테이너 단독 실행 기준", 12, 400, GR)
t(1540, 988, "docs/figures/make_pipeline_fig.py", 12, 400, GR, "end")

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{INK}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>'''
print(svg)
