"""구상안 전체 구조도 생성(PNG)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "구상안-전체-구조.png"
F = "C:/Windows/Fonts/malgun.ttf"
FB = "C:/Windows/Fonts/malgunbd.ttf"
W, H = 2400, 1180
BLACK, GRAY, LGRAY, LINE, ACC, ACCL = "#111111", "#555555", "#F2F2F2", "#9A9A9A", "#1F4E79", "#E8EEF5"
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)


def font(size, bold=False):
    return ImageFont.truetype(FB if bold else F, size)


def box(x, y, w, h, fill="white", outline=LINE, width=2):
    d.rectangle([x, y, x + w, y + h], fill=fill, outline=outline, width=width)


def text(x, y, s, size=22, bold=False, color=BLACK, maxw=None, gap=8):
    f = font(size, bold)
    lines = []
    for para in s.split("\n"):
        if maxw is None:
            lines.append(para); continue
        cur = ""
        for word in para.split(" "):
            t = (cur + " " + word).strip()
            if d.textlength(t, font=f) <= maxw:
                cur = t
            else:
                lines.append(cur); cur = word
        lines.append(cur)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=color)
        y += size + gap
    return y


def arrow(x1, y1, x2, y2, color=GRAY, width=3):
    d.line([x1, y1, x2, y2], fill=color, width=width)
    import math
    a = math.atan2(y2 - y1, x2 - x1); L = 14
    p1 = (x2 - L * math.cos(a - 0.45), y2 - L * math.sin(a - 0.45))
    p2 = (x2 - L * math.cos(a + 0.45), y2 - L * math.sin(a + 0.45))
    d.polygon([(x2, y2), p1, p2], fill=color)


# 제목
text(60, 36, "표와 이미지에 분산된 정보의 관계와 적용 조건을 보존하는 전처리 및 구조화 방안", 38, True)
text(60, 92, "전체 내용을 우선 추출하고 관계가 누락되거나 불확실한 영역에 한해 추가 분석한 뒤 값과 적용 조건을 연결해 저장함", 24, color=GRAY)
d.line([60, 140, W - 60, 140], fill=BLACK, width=2)

# 구간 머리글
TOP = 170
cols = [(60, 330, "입력"), (430, 760, "데이터 전처리"), (1230, 600, "데이터 구조화"), (1870, 470, "질의 시 활용")]
for x, w, t in cols:
    d.rectangle([x, TOP, x + w, TOP + 50], fill=ACC)
    text(x + 18, TOP + 8, t, 26, True, "white")
text(430 + 280, TOP + 12, "문서 등록 시점 1회", 20, color="white")
text(1230 + 250, TOP + 12, "문서 등록 시점 1회", 20, color="white")
text(1870 + 230, TOP + 12, "질문마다", 20, color="white")

# 입력
y0 = TOP + 80
box(60, y0, 330, 220, LGRAY)
text(80, y0 + 18, "기술문서(교범, 시험 기준, 규격)", 22, True, maxw=290)
text(80, y0 + 80, "PDF 문서\n텍스트 레이어, 벡터 도형", 21, maxw=290)
text(80, y0 + 150, "스캔 문서와 이미지\n텍스트 레이어 없음", 21, maxw=290)
box(60, y0 + 250, 330, 440)
text(80, y0 + 264, "사례: 가상 정비 문서", 22, True)
# 미니 도면(조립도)
mx, my = 80, y0 + 306
d.rectangle([mx, my, mx + 290, my + 120], outline=BLACK, width=1)
d.rectangle([mx + 150, my + 22, mx + 280, my + 108], outline=BLACK, width=2)
text(mx + 158, my + 26, "HV-202", 18, True)
for cx, cy, n in [(mx + 200, my + 78, "3"), (mx + 40, my + 50, "1"), (mx + 95, my + 88, "2")]:
    d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=BLACK, width=2)
    text(cx - 6, cy - 13, n, 18)
text(mx, my + 128, "조립도", 18, color=GRAY)
ty = my + 165
d.rectangle([mx, ty, mx + 290, ty + 70], outline=BLACK, width=1)
d.line([mx, ty + 35, mx + 290, ty + 35], fill=BLACK); d.line([mx + 60, ty, mx + 60, ty + 70], fill=BLACK); d.line([mx + 150, ty, mx + 150, ty + 70], fill=BLACK)
text(mx + 8, ty + 6, "항목", 18); text(mx + 68, ty + 6, "규격", 18); text(mx + 158, ty + 6, "토크(N·m)", 18)
text(mx + 8, ty + 41, "3", 18); text(mx + 68, ty + 41, "M8", 18); text(mx + 158, ty + 41, "25 *", 18)
text(mx, ty + 78, "* 건식 나사산 기준\n  윤활 시 M8 20 N·m", 17, color=GRAY, gap=4)

# 전처리 단계
px, pw = 430, 760
steps = [
    ("전체 기본 추출", "모든 페이지 대상, CPU 처리",
     "PDF 문서: 파서로 텍스트, 표 셀, 좌표, 벡터 도형 추출\n스캔 문서: 기본 OCR과 경량 시각 분석(도형, 선, 원 검출)으로 글자, 부품 상자, 체결부 추출"),
    ("관계 점검", "연결이 예상되는 명시적 참조 확인",
     "표의 각주 기호와 각주 문장의 대응, 그림의 체결부 수와 표의 행 수 일치, 표의 식별자가 그림에서 확인되는지 여부"),
    ("선택적 재분석", "문제가 확인된 영역에 한정",
     "해당 영역에 한해 고해상도 재처리 또는 소형 문서 VLM 적용. 해결되지 않은 연결은 미확정 상태로 원본과 함께 보존"),
]
sy = y0
for i, (h1, h2, body) in enumerate(steps):
    bh = 170
    box(px, sy, pw, bh, ACCL if i == 2 else "white", ACC if i == 2 else LINE, 3 if i == 2 else 2)
    d.ellipse([px + 18, sy + 18, px + 58, sy + 58], fill=ACC)
    text(px + 31, sy + 21, str(i + 1), 24, True, "white")
    text(px + 74, sy + 20, h1, 26, True)
    text(px + 74 + d.textlength(h1, font=font(26, True)) + 16, sy + 26, h2, 20, color=GRAY)
    text(px + 74, sy + 72, body, 20, maxw=pw - 100, gap=6)
    if i < 2:
        arrow(px + pw / 2, sy + bh, px + pw / 2, sy + bh + 38)
    sy += bh + 40
# 재분석 예시
text(px, sy - 28, "예시: 스캔본에서 그림의 체결부 수(8)와 표의 행 수(6)가 다르면 표 영역과 해당 원에 한해 재처리", 18, color=GRAY, maxw=pw)

# 구조화
sx, sw = 1230, 600
box(sx, y0, sw, 370)
text(sx + 20, y0 + 16, "정보 구조", 26, True)
text(sx + 20, y0 + 56, "대상, 속성 또는 관계, 값, 적용 조건, 출처로 저장", 20, color=GRAY)
cols5 = ["대상", "속성 또는 관계", "값", "적용 조건", "출처"]
cw = [95, 130, 85, 95, 155]
rows = [["체결부 3", "소속 부품", "HV-202", "없음", "조립도 원과 상자"],
        ["체결부 3", "규격", "M8", "없음", "표 3행"],
        ["체결부 3", "토크", "25 N·m", "건식", "표 3행"],
        ["체결부 3", "토크", "20 N·m", "윤활", "표 각주 *"]]
tx, tyy = sx + 20, y0 + 100
xx = tx
for c, wdt in zip(cols5, cw):
    d.rectangle([xx, tyy, xx + wdt, tyy + 40], fill=LGRAY, outline=LINE)
    text(xx + 6, tyy + 9, c, 16, True); xx += wdt
for r in rows:
    tyy += 40; xx = tx
    for c, wdt in zip(r, cw):
        d.rectangle([xx, tyy, xx + wdt, tyy + 40], outline=LINE)
        text(xx + 6, tyy + 9, c, 16); xx += wdt
text(sx + 20, tyy + 54, "출처는 이미지 영역, 표 셀, 각주 단위로 기록", 18, color=GRAY)

box(sx, y0 + 390, sw, 300)
text(sx + 20, y0 + 402, "연결 원칙", 26, True)
yy = y0 + 446
for t in ["표의 헤더, 셀, 각주는 문서 구조를 기준으로 연결",
          "그림의 체결부 번호와 부품 상자는 포함 관계 확인 후 연결. 공간적 근접을 근거로 확정하지 않음",
          "동일 대상에 조건별로 다른 값이 있으면 각각 보존",
          "각주가 규격이나 조건을 명시하면 그 기준으로 해당 행에 연결. 식별자는 표기 규칙 정규화 후 대조",
          "항공 기술문서 표준 S1000D의 적용성 개념을 PDF와 스캔 문서에 적용"]:
    d.ellipse([sx + 22, yy + 10, sx + 30, yy + 18], fill=ACC)
    yy = text(sx + 42, yy, t, 19, maxw=sw - 70, gap=5) + 8

# 활용
ux, uw = 1870, 470
box(ux, y0, uw, 370)
text(ux + 20, y0 + 16, "근거 구성", 26, True)
yy = y0 + 62
for i, t in enumerate(["질문의 대상과 조건 파악", "저장된 관계에서 소속 체결부와 값 조회", "조건이 일치하는 값, 조건, 출처로 근거 구성", "소형 로컬 LLM에 전달"]):
    yy = text(ux + 20, yy, f"{i + 1}. {t}", 20, maxw=uw - 40, gap=5) + 10
box(ux, y0 + 390, uw, 300)
text(ux + 20, y0 + 402, "질문 조건별 결과", 26, True)
yy = y0 + 446
for a, b in [("조건 지정(윤활)", "20 N·m와 출처"), ("조건 미지정", "건식 25 N·m와 윤활 20 N·m 병기"), ("기록 없는 조건", "해당 기준 부재로 답변 보류")]:
    text(ux + 20, yy, a, 20, True)
    yy = text(ux + 20, yy + 30, b, 19, color=GRAY, maxw=uw - 40) + 10

# 연결 화살표
arrow(390, y0 + 150, 430, y0 + 150)
arrow(1190, y0 + 165, 1230, y0 + 165)
arrow(1830, y0 + 165, 1870, y0 + 165)

# 하단 띠
by = 990
d.line([60, by - 14, W - 60, by - 14], fill=BLACK, width=2)
bands = [("제한된 연산 자원 대응", "전처리와 구조화는 등록 시점 1회 수행 후 재사용\nGPU 사용은 문제 영역의 재분석에 한정\n질의 시 필요한 값과 조건으로 입력 한정"),
         ("한계와 보완", "1차 추출에서 완전히 누락된 정보는 관계 점검으로 탐지 불가\n원본과의 표본 대조, 중요 정보의 별도 확인으로 보완"),
         ("검증 지표", "관계 연결 정확도, 질의응답 정답률\n문서당 처리 시간, VLM 호출 수, 질의당 입력 토큰 수"),
         ("사용 기술(공개 모델, 독립 실행)", "PDF 파서, 기본 OCR, OpenCV 도형 검출\n소형 문서 VLM Granite-Docling 258M\n소형 LLM Granite 4.1 3B")]
bx, bw = 60, (W - 120 - 3 * 30) / 4
for t, b in bands:
    box(bx, by, bw, 160, LGRAY, LGRAY)
    text(bx + 20, by + 16, t, 23, True)
    text(bx + 20, by + 62, b, 19, maxw=bw - 40, gap=7)
    bx += bw + 30

img.save(OUT)
print(OUT)
