"""한글 기술 문서 쪽 합성: 300 dpi A4 렌더와 정답 문자열, 열화 변형 생성"""
import json, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

FONT_R = os.path.expanduser('~/.fonts/Pretendard-Regular.otf')
FONT_B = os.path.expanduser('~/.fonts/Pretendard-SemiBold.otf')
DPI = 300
W, H = int(8.27 * DPI), int(11.69 * DPI)
pt = lambda p: int(p * DPI / 72)

TITLE = "7장 볼트와 너트의 체결 기준"
PARA = [
    "7-1. 일반 사항. 항공기 구조물에 사용하는 볼트는 규격에 맞는 재질과 표면 처리를 확인한 뒤 체결한다. 체결 토크는 표 7-1의 값을 따르며 윤활 여부에 따라 값이 달라진다.",
    "7-2. 토크 측정. 토크 렌치는 사용 전 교정 상태를 확인한다. 측정 범위의 20% 이하 구간에서는 사용하지 않는다. 체결 후 풀림 방지 와이어 또는 코터 핀을 적용한다.",
    "7-3. 주의. 카드뮴 도금 볼트를 티타늄 부품에 직접 체결하지 않는다. 손상된 나사산은 재사용하지 않으며 부품 번호가 확인되지 않는 볼트는 폐기한다.",
]
HEAD = ["부품 번호", "명칭", "나사 규격", "체결 토크(in-lb)"]
ROWS = [
    ["AN3-5A", "육각 볼트, 강", "10-32", "20~25"],
    ["AN4-7A", "육각 볼트, 강", "1/4-28", "50~70"],
    ["NAS6204-10", "고강도 볼트, 합금강", "1/4-28", "70~90"],
    ["MS20365-428", "자동 풀림 방지 너트", "1/4-28", "40~60"],
    ["AN960-416", "평와셔, 카드뮴 도금", "1/4", "-"],
    ["MS21042-4", "경량 풀림 방지 너트", "1/4-28", "50~70"],
]
NOTE = "주: 토크 값은 건조 상태 기준이며 윤활 시 표 값의 80%를 적용한다."
FOOT = "AC 43.13-1B 7장 참조 형식 · 합성 문서 · 2026-10-29"

def main(out):
    img = Image.new('L', (W, H), 255); d = ImageDraw.Draw(img)
    gt = []  # (text, box)
    def text(x, y, s, font):
        d.text((x, y), s, font=font, fill=0); b = d.textbbox((x, y), s, font=font); gt.append((s, [int(v) for v in b])); return b[3] - b[1]
    def wrap(s, font, maxw):
        words, lines, cur = s.split(' '), [], ''
        for w in words:
            cand = (cur + ' ' + w).strip()
            if d.textlength(cand, font=font) > maxw and cur: lines.append(cur); cur = w
            else: cur = cand
        if cur: lines.append(cur)
        return lines
    fT, fB, fR, fS = ImageFont.truetype(FONT_B, pt(16)), ImageFont.truetype(FONT_B, pt(10.5)), ImageFont.truetype(FONT_R, pt(10.5)), ImageFont.truetype(FONT_R, pt(9))
    m = pt(60); y = m
    y += text(m, y, TITLE, fT) + pt(14)
    for p in PARA:
        for ln in wrap(p, fR, W - 2 * m): y += text(m, y, ln, fR) + pt(5)
        y += pt(8)
    # 표
    y += pt(6); text(m, y, "표 7-1. 체결 토크", fB); y += pt(18)
    cw = [pt(110), pt(150), pt(90), pt(120)]; xs = [m]; 
    for c in cw: xs.append(xs[-1] + c)
    rh = pt(20); y0 = y
    for r, row in enumerate([HEAD] + ROWS):
        for c, cell in enumerate(row):
            text(xs[c] + pt(6), y + pt(4), cell, fB if r == 0 else fR)
        y += rh
    for r in range(len(ROWS) + 2): d.line([(xs[0], y0 + r * rh), (xs[-1], y0 + r * rh)], fill=0, width=3 if r in (0, 1, len(ROWS) + 1) else 2)
    for x in xs: d.line([(x, y0), (x, y)], fill=0, width=2)
    y += pt(10); y += text(m, y, NOTE, fS) + pt(30)
    text(m, H - m, FOOT, fS)
    os.makedirs(out, exist_ok=True)
    img.save(f'{out}/page300.png')
    json.dump([{'text': s, 'box': b} for s, b in gt], open(f'{out}/gt.json', 'w'), ensure_ascii=False, indent=1)
    base = np.array(img)
    def scan(a, deg, dpi, q, seed=0):
        rng = np.random.default_rng(seed)
        s = dpi / DPI; a = cv2.resize(a, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), deg, 1); a = cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), borderValue=255)
        a = cv2.GaussianBlur(a, (3, 3), 0.6)
        a = np.clip(a.astype(np.float32) + rng.normal(0, 10, a.shape), 0, 255).astype(np.uint8)
        _, enc = cv2.imencode('.jpg', a, [cv2.IMWRITE_JPEG_QUALITY, q]); return cv2.imdecode(enc, 0)
    for name, (deg, dpi, q) in {'clean200': (0, 200, 95), 'scan200': (0.4, 200, 50), 'scan150': (0.4, 150, 50), 'scan100': (0.4, 100, 50)}.items():
        cv2.imwrite(f'{out}/{name}.jpg', scan(base, deg, dpi, q))
    print('ok', len(gt), 'lines')
if __name__ == '__main__': main(sys.argv[1] if len(sys.argv) > 1 else 'out')
