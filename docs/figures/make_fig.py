#!/usr/bin/env python3
"""구상안 전체 그림(가로형 1600x900) SVG 생성."""
import html, sys

W, H = 1600, 900
ACC = "#1F4FD8"      # 강조색 1개(추가 분석 대상 표시)
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
t(60, 58, "표와 이미지에 분산된 정보의 관계와 적용 조건을 보존하는 전처리 및 구조화", 26, 600, ls="-0.5")
t(60, 86, "설계 전제: 폐쇄망 운용, 제한된 연산 자원, 독립 실행 가능한 공개 모델", 14, 400, GR)
t(1540, 86, "적용 대상: PDF와 스캔 형태의 기술문서(정비 교범, 시험 기준, 규격)", 14, 400, GR, "end")
hline(60, 1540, 104, INK, 1.2)

# ---------- 1단: 처리 흐름 ----------
t(60, 134, "처리 흐름", 13, 600, GR, ls="1")
cols = [
    ("입력", "", ["PDF, 스캔 문서", "그림, 표, 각주, 조항"], ["텍스트 레이어 유무 확인"]),
    ("1", "전체 기본 추출", ["모든 페이지 대상", "디지털: CPU 파서로 텍스트, 셀, 좌표", "도면: 벡터 객체와 좌표", "스캔: 기본 OCR, 도형과 선과 원 검출"], ["저비용 처리, GPU 불필요"]),
    ("2", "구조화와 관계 점검", ["항목: 대상, 속성 또는 관계, 값,", "적용 조건, 출처(영역, 셀, 각주 단위)", "점검: 각주 기호, 그림과 표의 대응,", "식별자 대조, 값 충돌"], ["문제 영역 목록 산출"]),
    ("3", "선택적 추가 분석", ["문제 영역에 한정", "고해상도 재처리 또는", "소형 시각언어모델(VLM) 재해석", "결과를 2단계에 재투입"], ["추가 분석 영역 수, 미해결 연결 수 측정"]),
    ("4", "저장", ["적용 조건과 출처를 함께 보존", "조건별 값은 각각 보존", "미확정 관계는 원본과 함께 보류", "문서 등록 시 1회 처리 후 재사용"], ["이후 질의에서 재처리 없음"]),
    ("5", "질의 시 전달", ["대상과 조건이 일치하는 항목 조회", "조건 미지정: 조건별 값 병기", "기록 없는 조건: 기준 부재 전달", "소형 로컬 LLM에 값, 조건, 출처 입력"], ["질의당 입력 토큰 최소화"]),
]
x0, y0, cw, ch, gap = 60, 150, 228, 190, 22
for i, (num, name, body, foot) in enumerate(cols):
    x = x0 + i * (cw + gap)
    rect(x, y0, cw, ch, stroke=LINE if i == 0 else INK, fill=FILL if i == 0 else "none")
    if name:
        t(x + 14, y0 + 30, num, 22, 700, ACC if num == "3" else INK)
        t(x + 40, y0 + 30, name, 17, 600)
    else:
        t(x + 14, y0 + 30, num, 17, 600)
    hline(x + 14, x + cw - 14, y0 + 42, LINE)
    lines(x + 14, y0 + 66, body, 13.5, 21)
    hline(x + 14, x + cw - 14, y0 + ch - 36, LINE)
    lines(x + 14, y0 + ch - 16, foot, 12.5, 18, GR)
    if i < len(cols) - 1:
        arrow(x + cw + 2, y0 + ch / 2, x + cw + gap - 2, y0 + ch / 2)
# 3단계에서 2단계로 되돌아가는 선
xa = x0 + 3 * (cw + gap) + cw / 2; xb = x0 + 2 * (cw + gap) + cw / 2; yb = y0 + ch
vline(xa, yb, yb + 18, ACC, 1.2); hline(xb, xa, yb + 18, ACC, 1.2); arrow(xb, yb + 18, xb, yb + 3, ACC, 1.2)
t((xa + xb) / 2, yb + 33, "재점검", 12, 500, ACC, "middle")

# ---------- 2단: 사례 ----------
Y2 = 400
t(60, Y2 + 12, "사례: 가상 정비 문서", 13, 600, GR, ls="1")
hline(60, 1540, Y2 + 20, LINE)
# 원본: 그림
gx, gy = 60, Y2 + 40
t(gx, gy + 14, "그림 1 조립도", 13.5, 600)
rect(gx, gy + 24, 170, 96, LINE)
rect(gx + 12, gy + 36, 70, 44, INK); t(gx + 18, gy + 50, "HV-200", 10.5, 500)
rect(gx + 90, gy + 36, 68, 72, INK); t(gx + 96, gy + 50, "HV-202", 10.5, 600)
for (cx, cy, n, acc) in [(gx + 40, gy + 68, "1", True), (gx + 66, gy + 68, "2", False), (gx + 124, gy + 86, "3", False), (gx + 124, gy + 66, "7", True)]:
    out.append(f'<circle cx="{cx}" cy="{cy}" r="8" stroke="{ACC if acc else INK}" fill="none" stroke-width="{1.6 if acc else 1}"/>')
    t(cx, cy + 4, n, 10, 600, ACC if acc else INK, "middle")
t(gx, gy + 138, "체결부 3은 HV-202 상자 안에 위치", 12, 400, GR)
# 원본: 표
tx = 260
t(tx, gy + 14, "표 1 체결부 토크", 13.5, 600)
rows = [("항목", "규격", "토크(N·m)"), ("1", "M6", "10 *"), ("2", "M10", "48 *"), ("3", "M8", "25 *")]
for r, row in enumerate(rows):
    yy = gy + 42 + r * 20
    for c, cell in enumerate(row):
        t(tx + c * 58, yy, cell, 12, 600 if r == 0 else 400)
    hline(tx, tx + 170, yy + 6, LINE if r else INK)
t(tx, gy + 138, "각주  * 건식 기준. 윤활 시 M8 20 N·m", 12, 400, GR)
# 화살표 원본 -> 항목
arrow(450, gy + 80, 486, gy + 80)
# 구조화 항목 표
ix = 496
t(ix, gy + 14, "구조화 항목", 13.5, 600)
hdr = ("대상", "속성 또는 관계", "값", "적용 조건", "출처")
widths = (70, 100, 70, 72, 150)
recs = [("체결부 3", "소속 부품", "HV-202", "없음", "그림 1 체결부 3 원, HV-202 상자"),
        ("체결부 3", "규격", "M8", "없음", "표 1 3행"),
        ("체결부 3", "토크", "25 N·m", "건식", "표 1 3행"),
        ("체결부 3", "토크", "20 N·m", "윤활", "표 1 각주 *")]
for r, row in enumerate([hdr] + recs):
    yy = gy + 42 + r * 20; xx = ix
    for c, cell in enumerate(row):
        t(xx, yy, cell, 12, 600 if r == 0 else 400); xx += widths[c]
    hline(ix, ix + sum(widths), yy + 6, LINE if r else INK)
t(60, gy + 160, "스캔본 추가 분석: 체결부 수 8과 행 수 6 불일치, 번호 1과 7 미판독", 12, 400, ACC)
t(60, gy + 178, "표 영역과 해당 원에 한해 고해상도 재처리 또는 VLM 재해석", 12, 400, ACC)
lines(ix, gy + 160, ["연결 원칙: 표는 헤더, 셀, 각주의 문서 구조 기준으로 연결",
                     "그림은 체결부 번호와 부품 상자의 포함 관계로 연결, 근접은 근거 아님",
                     "조건별 값 각각 보존. 식별자 정규화 뒤 대조. S1000D 적용성 개념 적용"], 12, 18, GR)
# 화살표 항목 -> 질의
qx = 1000
arrow(ix + sum(widths) + 12, gy + 80, qx - 12, gy + 80)
t(qx, gy + 14, "질의 시 전달", 13.5, 600)
t(qx, gy + 42, "질문: HV-202를 고정하는 체결부의 윤활 조건 토크 값", 12.5, 500)
hline(qx, 1540, gy + 50, INK)
q = [("윤활", "20 N·m, 윤활, 출처 표 1 각주 *"), ("조건 미지정", "건식 25 N·m와 윤활 20 N·m 병기"), ("기록 없는 조건", "기준 부재 전달, 필수 근거 없으면 보류")]
for r, (a, b) in enumerate(q):
    yy = gy + 70 + r * 22
    t(qx, yy, a, 12, 600); t(qx + 110, yy, b, 12)
    hline(qx, 1540, yy + 7, LINE)
t(qx, gy + 156, "고정 길이 분할 입력은 소속 관계가 텍스트에 없어 답변 불가", 12, 400, GR)

# ---------- 3단: 검증과 한계 ----------
Y3 = 652
hline(60, 1540, Y3, LINE)
t(60, Y3 + 28, "검증", 13, 600, GR, ls="1")
t(60, Y3 + 54, "비교군", 13, 600); lines(130, Y3 + 54, ["효율: 전체 페이지 OCR, 레이아웃 파서 기본 처리, 소형 VLM 전체 페이지 변환, 제안(기본 추출 뒤 문제 영역 한정 재처리)",
                                                "효과: 고정 길이 분할, 요소 단위 분할(마크다운 표와 각주), 페이지 전체 입력, 페이지 이미지 VLM 직접 입력, 제안"], 13, 22)
t(60, Y3 + 110, "지표", 13, 600); lines(130, Y3 + 110, ["효율: 페이지당 처리 시간, 최대 메모리, 추가 분석 영역 수, 미해결 연결 수",
                                                 "효과: 질의 유형별 정답률(값, 조건 포함, 그림 연결, 조건 미지정), 질의당 입력 토큰"], 13, 22)
vline(1010, Y3 + 14, Y3 + 150, LINE)
t(1030, Y3 + 28, "한계", 13, 600, GR, ls="1")
lines(1030, Y3 + 54, ["처음부터 누락된 객체와 잘못 인식된 관계는 관계 점검으로 발견되지 않음",
                      "대응: 원본과의 표본 대조, 중요 값의 별도 확인, 미확정 관계는 보류",
                      "OCR 재처리는 비용 절감이 없음. 절감은 페이지당 비용이 큰 VLM 처리에서 성립",
                      "실측은 합성 문서 기준. 실제 문서는 다단 배치와 여러 쪽에 걸친 표로 더 어려움"], 13, 22)
hline(60, 1540, Y3 + 170, INK, 1.2)
t(60, Y3 + 196, "사용 기술: CPU 문서 파서(텍스트 레이어, 벡터 객체, 표 구조), 기본 OCR, 도형 검출(선, 원, 윤곽선), 소형 시각언어모델(VLM) 영역 재해석, 조건 연결 항목 저장, 소형 로컬 LLM 질의응답", 13, 400, GR)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,4 L0,8 z" fill="{INK}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#FFFFFF"/>
{chr(10).join(out)}
</svg>'''
open(sys.argv[1], "w").write(svg)
print("ok", len(svg))
