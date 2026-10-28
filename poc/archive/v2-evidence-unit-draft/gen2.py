"""PoC v2 합성 기술문서 생성: 다단 헤더·병합 셀 표, 부품 배치 그림, 적용 조건 조항. 절반은 스캔본(텍스트 레이어 없음)."""
import json, random, os, subprocess, io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

random.seed(11)
OUT = "data"; os.makedirs(f"{OUT}/pdf", exist_ok=True); os.makedirs(f"{OUT}/tmp", exist_ok=True)
SYSTEMS = ["HYDRAULIC", "FUEL", "ENVIRONMENTAL CONTROL", "LANDING GEAR", "ELECTRICAL", "FLIGHT CONTROL"]
PREF = ["HV", "FP", "EC", "LG", "EL", "FC"]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

docs, facts = [], []
for d in range(12):
    sysi = d // 2; cfg = "A" if d % 2 == 0 else "B"
    comps = [f"{PREF[sysi]}-{200 + 10 * sysi + k}" for k in range(6)]
    groups = ["SUPPLY"] * 3 + ["RETURN"] * 3
    p_unit = "psi" if (d // 2) % 3 == 2 else "kPa"
    rows = []
    for k, c in enumerate(comps):
        tn = random.randrange(60, 120, 5) + (5 if cfg == "B" else 0)
        te = tn + random.randrange(10, 30, 5)
        pn_kpa = random.randrange(1500, 3000, 50) + (100 if cfg == "B" else 0)
        pe_kpa = pn_kpa + random.randrange(200, 600, 50)
        pn = round(pn_kpa / 6.895) if p_unit == "psi" else pn_kpa
        pe = round(pe_kpa / 6.895) if p_unit == "psi" else pe_kpa
        rows.append([groups[k], c, tn, te, pn, pe])
    scanned = d % 2 == 1 if d < 6 else d % 2 == 0   # 절반 스캔본, 구성 A·B 모두 포함
    docs.append({"doc": f"TDS-{101 + d}", "system": SYSTEMS[sysi], "config": cfg, "comps": comps, "rows": rows, "p_unit": p_unit, "scanned": scanned, "rev": "1"})
    for r in rows:
        for j, (attr, cond) in enumerate([("max_temperature", "normal"), ("max_temperature", "emergency"), ("max_pressure", "normal"), ("max_pressure", "emergency")]):
            unit = "°C" if attr == "max_temperature" else p_unit
            facts.append({"doc": f"TDS-{101 + d}", "target": r[1], "attr": attr, "cond": cond, "config": cfg, "value": r[2 + j], "unit": unit, "group": r[0]})


def figure_png(comps, path):
    W, H = 1400, 520
    im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im); f = ImageFont.truetype(FONT, 30)
    xs = [120 + i * 210 for i in range(6)]
    for i, c in enumerate(comps):
        y = 140 if i < 3 else 330
        x = xs[i] if i < 3 else xs[i - 3] + 520
        dr.rectangle([x, y, x + 170, y + 90], outline="black", width=4)
        dr.text((x + 20, y + 28), c, fill="black", font=f)
        if i not in (2, 5): dr.line([x + 170, y + 45, x + 210 + (0 if i < 3 else 0), y + 45], fill="black", width=4)
    dr.line([xs[2] + 170, 185, xs[0] + 520, 330], fill="black", width=4)
    im.save(path)


def draw_doc(doc, path):
    c = canvas.Canvas(path, pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 13); c.drawString(50, H - 55, f"TECHNICAL DATA SHEET {doc['doc']}   REV {doc['rev']}")
    c.setFont("Helvetica", 10)
    c.drawString(50, H - 80, f"1. SCOPE  This sheet defines operating limits for the {doc['system']} system components.")
    c.drawString(50, H - 96, f"2. APPLICABILITY  Limits in Table 1 apply to Configuration {doc['config']} only.")
    c.drawString(50, H - 112, "    Emergency limits are short-duration values (60 s maximum).")
    # 표: GROUP | COMPONENT | MAX TEMPERATURE (°C) [NORMAL|EMERG] | MAX PRESSURE (unit) [NORMAL|EMERG]
    x0, y0 = 50, H - 140
    cw = [70, 90, 85, 85, 85, 85]; rh = 20
    xs = [x0]; [xs.append(xs[-1] + w) for w in cw]
    c.setFont("Helvetica-Bold", 10); c.drawString(50, y0 + 6, "TABLE 1  OPERATING LIMITS")
    top = y0 - 4; nrows = 2 + len(doc["rows"])
    bottom = top - rh * nrows
    c.setLineWidth(1)
    c.rect(xs[0], bottom, xs[-1] - xs[0], top - bottom)
    # 헤더 선
    c.line(xs[2], top - rh, xs[6], top - rh)
    c.line(xs[0], top - 2 * rh, xs[6], top - 2 * rh)
    for i in [1, 2]: c.line(xs[i], top, xs[i], bottom)
    c.line(xs[4], top, xs[4], bottom)
    for i in [3, 5]: c.line(xs[i], top - rh, xs[i], bottom)
    # 본문 가로선(그룹 병합 고려: 첫 열은 그룹 경계에서만)
    for k in range(1, len(doc["rows"])):
        y = top - rh * (2 + k)
        x_start = xs[0] if doc["rows"][k][0] != doc["rows"][k - 1][0] else xs[1]
        c.line(x_start, y, xs[6], y)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString((xs[0] + xs[1]) / 2, top - rh - 4, "GROUP")
    c.drawCentredString((xs[1] + xs[2]) / 2, top - rh - 4, "COMPONENT")
    c.drawCentredString((xs[2] + xs[4]) / 2, top - rh + 6, "MAX TEMPERATURE (°C)")
    c.drawCentredString((xs[4] + xs[6]) / 2, top - rh + 6, f"MAX PRESSURE ({doc['p_unit']})")
    for i, t in enumerate(["NORMAL", "EMERG", "NORMAL", "EMERG"]):
        c.drawCentredString((xs[2 + i] + xs[3 + i]) / 2, top - 2 * rh + 6, t)
    c.setFont("Helvetica", 9)
    for k, r in enumerate(doc["rows"]):
        y = top - rh * (3 + k) + 6
        if k == 0 or r[0] != doc["rows"][k - 1][0]:
            span = sum(1 for q in doc["rows"] if q[0] == r[0])
            c.drawCentredString((xs[0] + xs[1]) / 2, top - rh * (2 + k) - rh * span / 2 - 3, r[0])
        for j in range(1, 6):
            c.drawCentredString((xs[j] + xs[j + 1]) / 2, y, str(r[j]))
    # 그림
    fp = f"{OUT}/tmp/{doc['doc']}_fig.png"; figure_png(doc["comps"], fp)
    fy = bottom - 40 - 190
    c.drawImage(ImageReader(fp), 50, fy, width=500, height=186)
    c.setFont("Helvetica-Bold", 10); c.drawString(50, fy - 16, "FIGURE 1  COMPONENT LAYOUT")
    c.setFont("Helvetica", 10)
    c.drawString(50, fy - 40, "3. NOTES  Components shown in Figure 1 correspond to Table 1 entries.")
    c.save()
    doc["fig_bbox_pt"] = [50, H - fy - 186, 550, H - fy]  # 좌상단 기준


def scan(pdf_path):
    base = pdf_path[:-4]
    subprocess.run(["pdftoppm", "-r", "100", "-png", "-singlefile", pdf_path, base + "_scan"], check=True)
    im = Image.open(base + "_scan.png").convert("L")
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(abs(hash(pdf_path)) % 2**32)
    a = a + rng.normal(0, 22, a.shape); a = np.clip(a, 0, 255).astype(np.uint8)
    im = Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=55); im = Image.open(buf)
    im.save(pdf_path, "PDF", resolution=100)
    os.remove(base + "_scan.png")


for doc in docs:
    p = f"{OUT}/pdf/{doc['doc']}.pdf"; draw_doc(doc, p)
    if doc["scanned"]: scan(p)

json.dump({"docs": docs, "facts": facts}, open(f"{OUT}/truth.json", "w"), indent=1, ensure_ascii=False)
print(len(docs), "docs", sum(d["scanned"] for d in docs), "scanned;", len(facts), "facts")
