"""합성 정비 문서 생성(체결 토크 사례).

문서 1건 = 범위 조항 + 그림 1(조립도: 부품 상자와 체결부 번호) + 표 1(체결부 토크, 각주 '*' 윤활 시 값) + 주기.
체결부와 부품의 소속 관계는 그림에만 있음. 토크 값은 표에, 윤활 조건 값은 각주에만 있음.
절반은 스캔본(텍스트 레이어 없음, 잡음·압축).
산출: data/pdf/*.pdf, data/truth.json, data/queries.json
"""
import io, json, os, random, sys
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = sys.argv[1] if len(sys.argv) > 1 else "data"
N_DOCS = 20
random.seed(21)
os.makedirs(f"{OUT}/pdf", exist_ok=True)

SYSTEMS = ["HYDRAULIC PUMP", "FUEL MANIFOLD", "ECS PACK", "MLG ACTUATOR", "GENERATOR", "FLAP DRIVE",
           "AVIONICS RACK", "OXYGEN REGULATOR", "ANTI-ICE VALVE", "APU MOUNT"]
PREF = ["HV", "FP", "EC", "LG", "EL", "FC", "AC", "OX", "AI", "AP"]
SIZES = {"M5": (5, 4), "M6": (10, 8), "M8": (25, 20), "M10": (48, 38), "M12": (85, 68)}  # dry, lubricated

docs, facts = [], []
for d in range(N_DOCS):
    sysi = d % len(SYSTEMS)
    rev = 1 + d // len(SYSTEMS)
    parts = [f"{PREF[sysi]}-{200 + 10 * sysi + k + (50 if rev == 2 else 0)}" for k in range(4)]
    n_items = 8
    items = []
    off = random.choice([-2, 0, 2])
    tq = {s: (v[0] + off, round((v[0] + off) * 0.8)) for s, v in SIZES.items()}
    for it in range(1, n_items + 1):
        part = parts[(it - 1) % 4] if it <= 4 else random.choice(parts)
        size = random.choice(list(SIZES))
        dry, lub = tq[size]
        items.append({"item": it, "part": part, "size": size, "dry": dry, "lub": lub})
    scanned = (d % 4) in (1, 2)
    doc = {"doc": f"MM-{32 + d:02d}-10-{rev:02d}", "system": SYSTEMS[sysi], "rev": rev, "parts": parts, "items": items, "scanned": scanned}
    docs.append(doc)
    for x in items:
        facts.append({"doc": doc["doc"], "item": x["item"], "part": x["part"], "size": x["size"], "dry": x["dry"], "lub": x["lub"]})


def draw_figure(c, doc, x0, y0, w, h):
    """조립도: 부품 상자 4개(부품 번호 표기), 체결부는 원 안의 번호. 원이 상자 경계 안에 있으면 그 부품에 체결됨."""
    boxes = []
    bw, bh = 150, 95
    pos = [(x0 + 20, y0 + h - bh - 20), (x0 + 20 + bw + 60, y0 + h - bh - 20),
           (x0 + 20, y0 + 20), (x0 + 20 + bw + 60, y0 + 20)]
    c.setLineWidth(1.2)
    for p, (bx, by) in zip(doc["parts"], pos):
        c.rect(bx, by, bw, bh)
        c.setFont("Helvetica", 9); c.drawString(bx + 6, by + bh - 14, p)
        boxes.append((p, bx, by, bw, bh))
    geo = {}
    used = {p: 0 for p in doc["parts"]}
    for x in doc["items"]:
        p, bx, by, bw_, bh_ = [b for b in boxes if b[0] == x["part"]][0]
        k = used[p]; used[p] += 1
        cx = bx + 30 + (k % 3) * 45; cy = by + 30 + (k // 3) * 35
        c.circle(cx, cy, 9, stroke=1, fill=0)
        c.setFont("Helvetica", 8); c.drawCentredString(cx, cy - 3, str(x["item"]))
        geo[x["item"]] = (cx, cy)
    c.setLineWidth(0.8)
    c.line(pos[0][0] + bw, pos[0][1] + bh / 2, pos[1][0], pos[1][1] + bh / 2)
    c.line(pos[2][0] + bw, pos[2][1] + bh / 2, pos[3][0], pos[3][1] + bh / 2)
    c.line(pos[0][0] + bw / 2, pos[0][1], pos[2][0] + bw / 2, pos[2][1] + bh)
    return boxes, geo


def draw_doc(doc, path):
    c = canvas.Canvas(path, pagesize=A4); W, H = A4
    c.setFont("Helvetica-Bold", 13); c.drawString(50, H - 55, f"MAINTENANCE MANUAL  TASK {doc['doc']}   REV {doc['rev']}")
    c.setFont("Helvetica", 10)
    c.drawString(50, H - 80, f"1. SCOPE  This task covers removal and installation of the {doc['system']} assembly.")
    c.drawString(50, H - 96, "2. APPLICABILITY  Torque values in Table 1 apply to the fasteners identified in Figure 1.")
    c.drawString(50, H - 112, "    Values are for dry threads unless noted otherwise.")
    # Figure 1
    fx, fy, fw, fh = 50, H - 140 - 260, 420, 250
    c.setFont("Helvetica-Bold", 10); c.drawString(50, fy + fh + 6, "FIGURE 1  ASSEMBLY VIEW")
    c.setLineWidth(0.5); c.rect(fx, fy, fw, fh)
    boxes, geo = draw_figure(c, doc, fx, fy, fw, fh)
    # Table 1
    ty = fy - 30
    c.setFont("Helvetica-Bold", 10); c.drawString(50, ty + 6, "TABLE 1  FASTENER TORQUE")
    cw = [60, 70, 110]; xs = [50]
    for w in cw: xs.append(xs[-1] + w)
    rh = 18; top = ty - 4; nrows = 1 + len(doc["items"]); bottom = top - rh * nrows
    c.setLineWidth(1); c.rect(xs[0], bottom, xs[-1] - xs[0], top - bottom)
    for i in [1, 2]: c.line(xs[i], top, xs[i], bottom)
    for k in range(nrows): c.line(xs[0], top - rh * (k + 1), xs[-1], top - rh * (k + 1))
    c.setFont("Helvetica-Bold", 8)
    for i, t in enumerate(["ITEM", "SIZE", "TORQUE (N·m)"]):
        c.drawCentredString((xs[i] + xs[i + 1]) / 2, top - rh + 6, t)
    c.setFont("Helvetica", 9)
    cells = {}
    for k, x in enumerate(doc["items"]):
        y = top - rh * (2 + k) + 6
        vals = [str(x["item"]), x["size"], f"{x['dry']} *"]
        for j, v in enumerate(vals):
            c.drawCentredString((xs[j] + xs[j + 1]) / 2, y, v)
        cells[x["item"]] = (xs[0], top - rh * (2 + k), xs[-1], top - rh * (1 + k))
    c.setFont("Helvetica", 8)
    fn_y = bottom - 14
    lubs = sorted({(x["size"], x["lub"]) for x in doc["items"]})
    c.drawString(50, fn_y, "* Dry thread. Lubricated thread: " + ", ".join(f"{s} {v} N·m" for s, v in lubs) + ".")
    c.setFont("Helvetica", 10)
    c.drawString(50, fn_y - 24, "3. NOTES  Item numbers in Table 1 refer to the callouts in Figure 1.")
    c.save()
    return {"figure": [fx, fy, fx + fw, fy + fh], "table": [xs[0], bottom, xs[-1], top], "footnote_y": fn_y,
            "boxes": [[p, bx, by, bx + bw, by + bh] for p, bx, by, bw, bh in boxes],
            "callouts": {str(k): v for k, v in geo.items()}, "cells": {str(k): v for k, v in cells.items()}}


def scan(pdf_path, seed):
    import pypdfium2 as pdfium
    page = pdfium.PdfDocument(pdf_path)[0]
    im = page.render(scale=130 / 72).to_pil().convert("L")
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(seed)
    a = np.clip(a + rng.normal(0, 18, a.shape), 0, 255).astype(np.uint8)
    im = Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.5))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=50)
    Image.open(buf).save(pdf_path, "PDF", resolution=130)


layout = {}
for i, doc in enumerate(docs):
    p = f"{OUT}/pdf/{doc['doc']}.pdf"; layout[doc["doc"]] = draw_doc(doc, p)
    if doc["scanned"]: scan(p, 1000 + i)

random.seed(7)
queries = []
for doc in docs:
    for x in doc["items"]:
        d = doc["doc"]
        queries.append({"type": "value", "doc": d, "item": x["item"], "cond": "dry",
                        "question": f"What is the torque for item {x['item']} in task {d}?", "answer": x["dry"]})
        queries.append({"type": "condition", "doc": d, "item": x["item"], "cond": "lubricated",
                        "question": f"What is the torque for item {x['item']} in task {d} when the thread is lubricated?", "answer": x["lub"]})
    # 그림 연결: 부품을 기준으로 체결부 찾기(부품당 체결부 1개인 경우에 한해 단일 정답)
    for p in doc["parts"]:
        its = [x for x in doc["items"] if x["part"] == p]
        if len(its) != 1: continue
        x = its[0]
        queries.append({"type": "figure", "doc": doc["doc"], "item": x["item"], "part": p, "cond": "lubricated",
                        "question": f"What torque applies to the fastener securing {p} in task {doc['doc']} when the thread is lubricated?", "answer": x["lub"]})
        queries.append({"type": "unspecified", "doc": doc["doc"], "item": x["item"], "part": p, "cond": None,
                        "question": f"What torque applies to the fastener securing {p} in task {doc['doc']}?", "answer": [x["dry"], x["lub"]]})
json.dump({"docs": docs, "facts": facts, "layout": layout}, open(f"{OUT}/truth.json", "w"), indent=1, ensure_ascii=False)
json.dump(queries, open(f"{OUT}/queries.json", "w"), indent=1, ensure_ascii=False)
from collections import Counter
print(len(docs), "docs,", sum(d["scanned"] for d in docs), "scanned,", len(facts), "facts,", len(queries), "queries", Counter(q["type"] for q in queries))
