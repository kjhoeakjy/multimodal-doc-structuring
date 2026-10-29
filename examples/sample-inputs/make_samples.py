"""표본 입력 묶음 생성: 보유 자료 복사와 합성 자료(기계 도면, 한글 보고서, 영문 벡터 보고서 PDF) 생성"""
import os, sys, shutil, json, math, random
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PUB = os.path.join(ROOT, 'examples', 'public-documents')
KO = os.path.join(ROOT, 'examples', 'korean-ocr', 'output')
FONT_R = os.path.expanduser('~/.fonts/Pretendard-Regular.otf'); FONT_B = os.path.expanduser('~/.fonts/Pretendard-SemiBold.otf')
OUT = os.path.join(HERE, 'input'); os.makedirs(OUT, exist_ok=True)
EXTRA = sys.argv[1] if len(sys.argv) > 1 else None   # 래스터 도면이 있는 폴더(선택)

def cp(src, dst):
    if os.path.exists(src):
        shutil.copy(src, os.path.join(OUT, dst)); return True
    return False

# 1. 보유 자료
cp(os.path.join(PUB, 'pid', 'input', 'C01.svg'), 'pid-standard-vector.svg')
cp(os.path.join(PUB, 'pid', 'input', 'DP.svg'), 'pid-plant-complex-vector.svg')
cp(os.path.join(PUB, 'pid', 'input', 'DL.svg'), 'pid-lab-vector.svg')
cp(os.path.join(PUB, 'pages', 'input', 'nist-ftc-07.jpg'), 'mech-iso-tolerance-real.jpg')
cp(os.path.join(PUB, 'pages', 'input', 'faa_p10.jpg'), 'faa-bolt-table-illustrations.jpg')
cp(os.path.join(PUB, 'pages', 'input', 'faa_p9.png'), 'faa-torque-table.png')
cp(os.path.join(PUB, 'pages', 'input', 'faa_p5.jpg'), 'faa-text-page.jpg')
cp(os.path.join(PUB, 'pages', 'input', 'faa_scan.jpg'), 'faa-torque-table-scan.jpg')
cp(os.path.join(KO, 'scan200.jpg'), 'ko-table-text-scan200.jpg')
if EXTRA:
    cp(os.path.join(EXTRA, 'C01_200.png'), 'pid-standard-200dpi.png')
    cp(os.path.join(EXTRA, 'C01_scan200.png'), 'pid-standard-scan.png')
    cp(os.path.join(EXTRA, 'DP_150.png'), 'pid-plant-complex-150dpi.png')
# 사진(scikit-image 동봉 공개 사진)
import skimage
sd = os.path.join(os.path.dirname(skimage.__file__), 'data')
cp(os.path.join(sd, 'rocket.jpg'), 'photo-rocket-launch.jpg')
cp(os.path.join(sd, 'page.png'), 'photo-of-text-page.png')
cp(os.path.join(sd, 'astronaut.png'), 'photo-astronaut.png')

# 2. 합성 기계 도면(플랜지: 원·호·치수선·지시선·표제란) SVG, 벡터 + 200 dpi 래스터
def flange_svg(path):
    W, H = 297, 210
    L = []
    a = L.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}" font-family="Arial" fill="none" stroke="#000">')
    a(f'<rect width="{W}" height="{H}" fill="#fff" stroke="none"/>')
    a(f'<rect x="10" y="10" width="{W-20}" height="{H-20}" stroke-width="0.7"/>')
    cx, cy = 90, 100
    a(f'<circle cx="{cx}" cy="{cy}" r="60" stroke-width="0.5"/>')          # 외경
    a(f'<circle cx="{cx}" cy="{cy}" r="28" stroke-width="0.5"/>')          # 내경
    a(f'<circle cx="{cx}" cy="{cy}" r="46" stroke-width="0.25" stroke-dasharray="4 1.5 0.5 1.5"/>')  # 볼트 원
    for i in range(8):                                                     # 볼트 구멍 8개
        t = math.radians(i * 45 + 22.5); x, y = cx + 46 * math.cos(t), cy + 46 * math.sin(t)
        a(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" stroke-width="0.5"/>')
        a(f'<path d="M{x-6:.2f},{y:.2f} L{x+6:.2f},{y:.2f} M{x:.2f},{y-6:.2f} L{x:.2f},{y+6:.2f}" stroke-width="0.18"/>')
    a(f'<path d="M{cx-66},{cy} L{cx+66},{cy} M{cx},{cy-66} L{cx},{cy+66}" stroke-width="0.18" stroke-dasharray="6 1.5 1 1.5"/>')
    # 측면도(우측): 두께와 허브, 필릿 호
    sx = 200
    a(f'<path d="M{sx},{cy-60} L{sx+14},{cy-60} L{sx+14},{cy-34} Q{sx+14},{cy-30} {sx+18},{cy-30} L{sx+34},{cy-30} L{sx+34},{cy+30} L{sx+18},{cy+30} Q{sx+14},{cy+30} {sx+14},{cy+34} L{sx+14},{cy+60} L{sx},{cy+60} Z" stroke-width="0.5"/>')
    a(f'<path d="M{sx},{cy-28} L{sx+34},{cy-28} M{sx},{cy+28} L{sx+34},{cy+28}" stroke-width="0.5"/>')
    for yy in range(-58, 60, 4):   # 해칭
        a(f'<path d="M{sx},{cy+yy} L{sx+14},{cy+yy-14}" stroke-width="0.15"/>')
    # 치수선
    def dim(x0, y0, x1, y1, text, off=0, vert=False):
        a(f'<path d="M{x0},{y0} L{x1},{y1}" stroke-width="0.18"/>')
        a(f'<path d="M{x0},{y0} l2,-1 l0,2 z M{x1},{y1} l-2,-1 l0,2 z" fill="#000" stroke="none"/>' if not vert else f'<path d="M{x0},{y0} l-1,2 l2,0 z M{x1},{y1} l-1,-2 l2,0 z" fill="#000" stroke="none"/>')
        tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        a(f'<text x="{tx}" y="{ty - 1.2 if not vert else ty}" font-size="3.2" fill="#000" stroke="none" text-anchor="middle"{" transform=\"rotate(-90 %s %s)\"" % (tx, ty) if vert else ""}>{text}</text>')
    dim(cx - 60, cy + 72, cx + 60, cy + 72, 'Ø120'); a(f'<path d="M{cx-60},{cy+62} L{cx-60},{cy+74} M{cx+60},{cy+62} L{cx+60},{cy+74}" stroke-width="0.18"/>')
    dim(cx - 28, cy - 72, cx + 28, cy - 72, 'Ø56 H7'); a(f'<path d="M{cx-28},{cy-62} L{cx-28},{cy-74} M{cx+28},{cy-62} L{cx+28},{cy-74}" stroke-width="0.18"/>')
    dim(sx, cy - 72, sx + 14, cy - 72, '14', vert=False); dim(sx + 44, cy - 60, sx + 44, cy + 60, '120', vert=True)
    dim(sx, cy + 72, sx + 34, cy + 72, '34')
    # 지시선 주기
    t = math.radians(22.5); hx, hy = cx + 46 * math.cos(t), cy + 46 * math.sin(t)
    a(f'<path d="M{hx+3:.2f},{hy-3:.2f} L{hx+22:.2f},{hy-22:.2f} L{hx+40:.2f},{hy-22:.2f}" stroke-width="0.18"/>')
    a(f'<text x="{hx+23:.2f}" y="{hy-23.5:.2f}" font-size="3.2" fill="#000" stroke="none">8 x Ø9 THRU</text>')
    a(f'<text x="{hx+23:.2f}" y="{hy-19:.2f}" font-size="3.2" fill="#000" stroke="none">EQ SP ON Ø92 B.C.</text>')
    a(f'<text x="{sx+36}" y="{cy-36}" font-size="3.2" fill="#000" stroke="none">R4 (2 PL)</text>')
    a(f'<path d="M{sx+35},{cy-35} L{sx+17},{cy-31}" stroke-width="0.18"/>')
    # 표제란
    bx, by = W - 10 - 110, H - 10 - 32
    a(f'<rect x="{bx}" y="{by}" width="110" height="32" stroke-width="0.5"/>')
    a(f'<path d="M{bx},{by+8} L{bx+110},{by+8} M{bx},{by+16} L{bx+110},{by+16} M{bx},{by+24} L{bx+110},{by+24} M{bx+40},{by} L{bx+40},{by+32} M{bx+75},{by+8} L{bx+75},{by+32}" stroke-width="0.3"/>')
    rows = [('TITLE', 'FLANGE, MOUNTING', ''), ('PART NO', 'FL-2040-A', 'REV B'), ('MATERIAL', 'AL 6061-T6', 'SCALE 1:1'), ('FINISH', 'ANODIZE CL2', 'SHT 1/1')]
    for i, (k, v, r) in enumerate(rows):
        a(f'<text x="{bx+2}" y="{by+6+i*8}" font-size="3" fill="#000" stroke="none">{k}</text><text x="{bx+42}" y="{by+6+i*8}" font-size="3" fill="#000" stroke="none">{v}</text><text x="{bx+77}" y="{by+6+i*8}" font-size="3" fill="#000" stroke="none">{r}</text>')
    a('<text x="14" y="20" font-size="4" font-weight="bold" fill="#000" stroke="none">NOTES: 1. BREAK ALL SHARP EDGES 0.5 MAX  2. DIMENSIONS IN MM  3. TOLERANCE ±0.2 UNLESS NOTED</text>')
    a('</svg>')
    open(path, 'w', encoding='utf-8').write('\n'.join(L))

flange_svg(os.path.join(OUT, 'mech-flange-synthetic-vector.svg'))
import pymupdf
doc = pymupdf.open(os.path.join(OUT, 'mech-flange-synthetic-vector.svg')); pix = doc[0].get_pixmap(dpi=200); pix.save(os.path.join(OUT, 'mech-flange-synthetic-200dpi.png'))

# 3. 합성 한글 보고서 쪽(제목, 문단, 막대 그래프 그림과 설명문, 표)
def ko_report(path):
    DPI = 200; W, H = int(8.27 * DPI), int(11.69 * DPI); pt = lambda p: int(p * DPI / 72)
    img = Image.new('L', (W, H), 255); d = ImageDraw.Draw(img)
    fT, fH, fR, fS = ImageFont.truetype(FONT_B, pt(15)), ImageFont.truetype(FONT_B, pt(11)), ImageFont.truetype(FONT_R, pt(10.5)), ImageFont.truetype(FONT_R, pt(9))
    m = pt(60); y = m
    def wrap(s, font, maxw):
        words, lines, cur = s.split(' '), [], ''
        for w in words:
            cand = (cur + ' ' + w).strip()
            if d.textlength(cand, font=font) > maxw and cur: lines.append(cur); cur = w
            else: cur = cand
        return lines + ([cur] if cur else [])
    def para(s, font=fR, gap=5):
        nonlocal y
        for ln in wrap(s, font, W - 2 * m):
            d.text((m, y), ln, font=font, fill=0); y += pt(font.size * 72 / DPI) + pt(gap)
        y += pt(6)
    d.text((m, y), "착륙장치 유압 계통 점검 결과 보고", font=fT, fill=0); y += pt(26)
    d.text((m, y), "1. 개요", font=fH, fill=0); y += pt(18)
    para("본 보고는 2026년 3분기 정기 점검에서 확인한 착륙장치 유압 계통의 상태와 조치 사항을 정리한 것이다. 점검 대상은 주 착륙장치 작동기 2기와 전방 착륙장치 조향 작동기 1기이며 점검 기준은 정비 교범 32장을 따랐다.")
    d.text((m, y), "2. 측정 결과", font=fH, fill=0); y += pt(18)
    para("작동기별 내부 누설량을 3회 측정한 평균은 그림 1과 같다. 좌측 주 착륙장치 작동기의 누설량이 허용 한계의 80%에 도달해 다음 점검 주기 전 교체를 권고한다.")
    # 그림 1: 막대 그래프
    gx, gy, gw, gh = m + pt(20), y, pt(300), pt(150)
    d.rectangle([gx, gy, gx + gw, gy + gh], outline=0, width=2)
    vals = [("L/H MLG", 3.2), ("R/H MLG", 1.9), ("NLG", 1.1)]; lim = 4.0
    for i, (nm, v) in enumerate(vals):
        bx0 = gx + pt(30) + i * pt(90); bh = int(gh * 0.8 * v / lim)
        d.rectangle([bx0, gy + gh - pt(12) - bh, bx0 + pt(50), gy + gh - pt(12)], fill=60 + i * 60, outline=0)
        d.text((bx0 + pt(8), gy + gh - pt(10)), nm, font=fS, fill=0); d.text((bx0 + pt(14), gy + gh - pt(20) - bh), f"{v}", font=fS, fill=0)
    d.line([gx, gy + gh - pt(12) - int(gh * 0.8), gx + gw, gy + gh - pt(12) - int(gh * 0.8)], fill=0, width=2)
    d.text((gx + gw - pt(80), gy + gh - pt(12) - int(gh * 0.8) - pt(12)), "허용 한계 4.0", font=fS, fill=0)
    d.text((gx + pt(2), gy + pt(2)), "누설량 (cc/min)", font=fS, fill=0)
    y = gy + gh + pt(6); d.text((gx, y), "그림 1. 작동기별 내부 누설량 평균(3회 측정)", font=fS, fill=0); y += pt(24)
    d.text((m, y), "3. 조치 사항", font=fH, fill=0); y += pt(18)
    head = ["항목", "부품 번호", "조치", "기한"]
    rows = [["L/H MLG 작동기", "114A3200-5", "교체", "2026-11-30"], ["R/H MLG 작동기", "114A3200-5", "추적 점검", "다음 주기"], ["NLG 조향 작동기", "114A3410-2", "이상 없음", "-"], ["유압유", "MIL-PRF-83282", "보충 0.4 L", "완료"]]
    cw = [pt(120), pt(110), pt(90), pt(90)]; xs = [m]
    for c in cw: xs.append(xs[-1] + c)
    rh = pt(20); y0 = y
    for r, row in enumerate([head] + rows):
        for c, cell in enumerate(row):
            d.text((xs[c] + pt(5), y + pt(4)), cell, font=fH if r == 0 else fR, fill=0)
        y += rh
    for r in range(len(rows) + 2): d.line([(xs[0], y0 + r * rh), (xs[-1], y0 + r * rh)], fill=0, width=3 if r in (0, 1, len(rows) + 1) else 2)
    for x in xs: d.line([(x, y0), (x, y)], fill=0, width=2)
    y += pt(8); d.text((m, y), "표 1. 조치 사항", font=fS, fill=0); y += pt(24)
    para("4. 결론. 좌측 주 착륙장치 작동기는 교체 부품 입고 즉시 교체하고, 교체 후 작동 시험과 누설 재측정을 수행한다. 나머지 항목은 다음 정기 점검에서 재확인한다.")
    d.text((m, H - m), "합성 문서 · 2026-10-29", font=fS, fill=0)
    img.save(path, dpi=(DPI, DPI))
ko_report(os.path.join(OUT, 'ko-report-synthetic.png'))

# 4. 합성 영문 벡터 보고서 PDF(문자, 표, 선 그래프)
def en_report_pdf(path):
    doc = pymupdf.open(); page = doc.new_page(width=595, height=842)
    page.insert_text((56, 70), "Hydraulic System Inspection Summary", fontsize=16, fontname="helv")
    txt = ("This summary records the third quarter inspection of the main and nose landing gear hydraulic actuators. "
           "Internal leakage was measured three times per actuator at 3000 psi with fluid at 40 C. Results are listed in Table 1 and plotted in Figure 1.")
    page.insert_textbox(pymupdf.Rect(56, 90, 539, 150), txt, fontsize=10.5, fontname="helv")
    # 표
    x0, y0 = 56, 165; cw = [150, 110, 110, 110]; rh = 20
    rows = [["Actuator", "Part number", "Leakage cc/min", "Action"], ["L/H MLG", "114A3200-5", "3.2", "Replace"], ["R/H MLG", "114A3200-5", "1.9", "Monitor"], ["NLG steering", "114A3410-2", "1.1", "None"]]
    for r, row in enumerate(rows):
        x = x0
        for c, cell in enumerate(row):
            page.insert_text((x + 4, y0 + r * rh + 14), cell, fontsize=9.5, fontname="hebo" if r == 0 else "helv"); x += cw[c]
    for r in range(len(rows) + 1):
        page.draw_line((x0, y0 + r * rh), (x0 + sum(cw), y0 + r * rh), width=1.2 if r in (0, 1, len(rows)) else 0.6)
    x = x0
    for c in cw + [0]:
        page.draw_line((x, y0), (x, y0 + len(rows) * rh), width=0.6); x += c
    page.insert_text((56, y0 + len(rows) * rh + 16), "Table 1. Leakage by actuator (mean of three measurements)", fontsize=8.5, fontname="helv")
    # 선 그래프
    gx, gy, gw, gh = 56, 290, 300, 160
    page.draw_rect(pymupdf.Rect(gx, gy, gx + gw, gy + gh), width=0.8)
    pts = [(0, 1.2), (1, 1.6), (2, 2.1), (3, 2.4), (4, 3.2)]
    P = [(gx + 30 + i * 60, gy + gh - 20 - v / 4.0 * (gh - 40)) for i, v in pts]
    for a_, b_ in zip(P, P[1:]):
        page.draw_line(a_, b_, width=1.5)
    for (px_, py_), (i, v) in zip(P, pts):
        page.draw_circle((px_, py_), 2.5, width=1); page.insert_text((px_ - 6, gy + gh - 6), f"Q{i+1}" if i < 4 else "Q3", fontsize=7.5, fontname="helv")
    page.draw_line((gx, gy + gh - 20 - (gh - 40)), (gx + gw, gy + gh - 20 - (gh - 40)), width=0.5, dashes="[3 2] 0")
    page.insert_text((gx + gw - 70, gy + 18), "limit 4.0 cc/min", fontsize=7.5, fontname="helv")
    page.insert_text((56, gy + gh + 16), "Figure 1. L/H MLG actuator leakage trend over five inspections", fontsize=8.5, fontname="helv")
    page.insert_textbox(pymupdf.Rect(56, 480, 539, 560), "Conclusion. The left main landing gear actuator (114A3200-5) has reached 80 percent of the allowable leakage and is scheduled for replacement before the next inspection interval. A functional test and leakage re-measurement follow the replacement.", fontsize=10.5, fontname="helv")
    page.insert_text((56, 800), "Synthetic document, 2026-10-29", fontsize=8, fontname="helv")
    doc.save(path)
en_report_pdf(os.path.join(OUT, 'en-report-synthetic-vector.pdf'))
# 같은 보고서의 150 dpi 스캔 모양
doc = pymupdf.open(os.path.join(OUT, 'en-report-synthetic-vector.pdf')); pix = doc[0].get_pixmap(dpi=150)
a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, 0].copy()
M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), -0.3, 1); a = cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), borderValue=255)
a = np.clip(a.astype(np.float32) + np.random.default_rng(1).normal(0, 8, a.shape), 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(OUT, 'en-report-synthetic-scan150.jpg'), a, [cv2.IMWRITE_JPEG_QUALITY, 55])
print(sorted(os.listdir(OUT)))
