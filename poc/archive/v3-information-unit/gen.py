"""합성 기술문서 생성.

문서 1건 = 범위·적용 조건 조항 + 다단 헤더·병합 셀 표 + 부품 배치 그림 + 주석.
같은 계통의 Configuration A·B 문서가 쌍으로 존재해 적용 조건을 놓치면 다른 값을 고르게 됨.
절반은 스캔본(텍스트 레이어 없음, 잡음·압축).
산출: data/pdf/*.pdf, data/truth.json, data/queries.json
"""
import io, json, os, random, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

OUT = sys.argv[1] if len(sys.argv) > 1 else "data"
N_SYSTEMS = 10
random.seed(11)
os.makedirs(f"{OUT}/pdf", exist_ok=True); os.makedirs(f"{OUT}/tmp", exist_ok=True)

SYSTEMS = ["HYDRAULIC", "FUEL", "ENVIRONMENTAL CONTROL", "LANDING GEAR", "ELECTRICAL", "FLIGHT CONTROL",
           "AVIONICS COOLING", "OXYGEN", "ANTI-ICE", "APU"]
PREF = ["HV", "FP", "EC", "LG", "EL", "FC", "AC", "OX", "AI", "AP"]
ATTRS = [("max_temperature", "normal"), ("max_temperature", "emergency"), ("max_pressure", "normal"), ("max_pressure", "emergency")]


def font(size):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf", "/Library/Fonts/Arial Bold.ttf"]:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()


docs, facts = [], []
for d in range(2 * N_SYSTEMS):
    sysi, cfg = d // 2, ("A" if d % 2 == 0 else "B")
    comps = [f"{PREF[sysi]}-{200 + 10 * sysi + k}" for k in range(6)]
    groups = ["SUPPLY"] * 3 + ["RETURN"] * 3
    p_unit = "psi" if sysi % 3 == 2 else "kPa"
    rows = []
    for k, c in enumerate(comps):
        tn = random.randrange(60, 120, 5) + (5 if cfg == "B" else 0)
        te = tn + random.randrange(10, 30, 5)
        pn_kpa = random.randrange(1500, 3000, 50) + (100 if cfg == "B" else 0)
        pe_kpa = pn_kpa + random.randrange(200, 600, 50)
        pn, pe = (round(pn_kpa / 6.895), round(pe_kpa / 6.895)) if p_unit == "psi" else (pn_kpa, pe_kpa)
        rows.append([groups[k], c, tn, te, pn, pe])
    scanned = (d % 4) in (1, 2)   # A·B 양쪽에 스캔본 포함
    doc = {"doc": f"TDS-{101 + d}", "system": SYSTEMS[sysi], "config": cfg, "comps": comps, "rows": rows, "p_unit": p_unit, "scanned": scanned}
    docs.append(doc)
    for r in rows:
        for j, (attr, cond) in enumerate(ATTRS):
            facts.append({"doc": doc["doc"], "target": r[1], "attr": attr, "cond": cond, "config": cfg,
                          "value": r[2 + j], "unit": "°C" if attr == "max_temperature" else p_unit, "group": r[0], "row": rows.index(r)})


def figure_png(comps, path):
    W, H = 1400, 520
    im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im); f = font(30)
    xs = [120 + i * 210 for i in range(3)]
    for i, c in enumerate(comps):
        y = 140 if i < 3 else 330
        x = xs[i % 3] + (0 if i < 3 else 520)
        dr.rectangle([x, y, x + 170, y + 90], outline="black", width=4)
        dr.text((x + 20, y + 28), c, fill="black", font=f)
        if i % 3 != 2: dr.line([x + 170, y + 45, x + 210, y + 45], fill="black", width=4)
    dr.line([xs[2] + 170, 185, xs[0] + 520, 330], fill="black", width=4)
    im.save(path)


def draw_doc(doc, path):
    c = canvas.Canvas(path, pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 13); c.drawString(50, H - 55, f"TECHNICAL DATA SHEET {doc['doc']}   REV 1")
    c.setFont("Helvetica", 10)
    c.drawString(50, H - 80, f"1. SCOPE  This sheet defines operating limits for the {doc['system']} system components.")
    c.drawString(50, H - 96, f"2. APPLICABILITY  Limits in Table 1 apply to Configuration {doc['config']} only.")
    c.drawString(50, H - 112, "    Emergency limits are short-duration values (60 s maximum).")
    x0, y0 = 50, H - 140
    cw = [70, 90, 85, 85, 85, 85]; rh = 20
    xs = [x0]
    for w in cw: xs.append(xs[-1] + w)
    c.setFont("Helvetica-Bold", 10); c.drawString(50, y0 + 6, "TABLE 1  OPERATING LIMITS")
    top = y0 - 4; nrows = 2 + len(doc["rows"]); bottom = top - rh * nrows
    c.setLineWidth(1); c.rect(xs[0], bottom, xs[-1] - xs[0], top - bottom)
    c.line(xs[2], top - rh, xs[6], top - rh); c.line(xs[0], top - 2 * rh, xs[6], top - 2 * rh)
    for i in [1, 2, 4]: c.line(xs[i], top, xs[i], bottom)
    for i in [3, 5]: c.line(xs[i], top - rh, xs[i], bottom)
    for k in range(1, len(doc["rows"])):
        y = top - rh * (2 + k)
        c.line(xs[0] if doc["rows"][k][0] != doc["rows"][k - 1][0] else xs[1], y, xs[6], y)
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
        for j in range(1, 6): c.drawCentredString((xs[j] + xs[j + 1]) / 2, y, str(r[j]))
    fp = f"{OUT}/tmp/{doc['doc']}_fig.png"; figure_png(doc["comps"], fp)
    fy = bottom - 40 - 190
    c.drawImage(ImageReader(fp), 50, fy, width=500, height=186)
    c.setFont("Helvetica-Bold", 10); c.drawString(50, fy - 16, "FIGURE 1  COMPONENT LAYOUT")
    c.setFont("Helvetica", 10)
    c.drawString(50, fy - 40, "3. NOTES  Components shown in Figure 1 correspond to Table 1 entries.")
    c.save()


def render(pdf_path, dpi):
    import pypdfium2 as pdfium
    page = pdfium.PdfDocument(pdf_path)[0]
    return page.render(scale=dpi / 72).to_pil().convert("L")


def scan(pdf_path, seed):
    im = render(pdf_path, 110)
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(seed)
    a = np.clip(a + rng.normal(0, 22, a.shape), 0, 255).astype(np.uint8)
    im = Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.6))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=55)
    Image.open(buf).save(pdf_path, "PDF", resolution=110)


for i, doc in enumerate(docs):
    p = f"{OUT}/pdf/{doc['doc']}.pdf"; draw_doc(doc, p)
    if doc["scanned"]: scan(p, 1000 + i)

# 질의: 조회·비교·설명·소속(그림·표 대응)
random.seed(5)
queries = []
F = {(f["target"], f["attr"], f["cond"], f["config"]): f for f in facts}
by_doc = {d["doc"]: d for d in docs}
for f in random.sample(facts, 120):
    queries.append({"type": "lookup", "target": f["target"], "attr": f["attr"], "cond": f["cond"], "config": f["config"],
                    "question": f"What is the {f['attr'].replace('_', ' ')} of {f['target']} under {f['cond']} operation in Configuration {f['config']}?",
                    "answer": f"{f['value']} {f['unit']}", "value": f["value"], "unit": f["unit"], "doc": f["doc"]})
for _ in range(40):
    d = random.choice(docs); a, b = random.sample(d["comps"], 2); attr, cond = random.choice(ATTRS)
    fa, fb = F[(a, attr, cond, d["config"])], F[(b, attr, cond, d["config"])]
    if fa["value"] == fb["value"]: continue
    queries.append({"type": "compare", "target": a, "target2": b, "attr": attr, "cond": cond, "config": d["config"],
                    "question": f"In Configuration {d['config']}, which has the higher {attr.replace('_', ' ')} under {cond} operation, {a} or {b}?",
                    "answer": a if fa["value"] > fb["value"] else b, "doc": d["doc"]})
for d in random.sample(docs, 20):
    queries.append({"type": "explain", "target": None, "config": d["config"],
                    "question": f"For the {d['system']} system in Configuration {d['config']}, how long may an emergency limit be sustained?",
                    "answer": "60 s", "doc": d["doc"]})
for _ in range(20):
    d = random.choice(docs); c = random.choice(d["comps"]); g = [r[0] for r in d["rows"] if r[1] == c][0]
    queries.append({"type": "membership", "target": c, "config": d["config"],
                    "question": f"Which group does {c} belong to in Configuration {d['config']}: SUPPLY or RETURN?",
                    "answer": g, "doc": d["doc"]})

json.dump({"docs": docs, "facts": facts}, open(f"{OUT}/truth.json", "w"), indent=1, ensure_ascii=False)
json.dump(queries, open(f"{OUT}/queries.json", "w"), indent=1, ensure_ascii=False)
print(len(docs), "docs,", sum(d["scanned"] for d in docs), "scanned,", len(facts), "facts,", len(queries), "queries")
