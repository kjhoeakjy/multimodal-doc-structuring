"""합성 기술문서 생성: 구역 위치도 + 구역별 점검 주기 표 + 각주. 디지털 PDF와 스캔본(PNG, 텍스트 레이어 없음)."""
import json, random, io
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import numpy as np, cv2, pypdfium2 as pdfium

OUT = Path(__file__).parent / "data"
CONDS = [
    "Normal operating environment.",
    "Salt-laden or sand/dust environment.",
    "Operation from unpaved runways.",
    "Aircraft parked outdoors more than 30 days.",
]
ABSENT = ["arctic cold-weather operation", "high-altitude airfield operation"]
W, H = A4


def make_doc(i, rng):
    zones = sorted(rng.sample(range(211, 260), 3))
    # 구역 경계(pt, 좌하단 기준)
    fx, fy, fw, fh = 70, 430, 455, 230
    zw = fw / 3
    zrects = {z: (fx + k * zw, fy, zw, fh) for k, z in enumerate(zones)}
    parts, used = {}, set()
    for z, (x, y, w, h) in zrects.items():
        for _ in range(rng.randint(2, 3)):
            while True:
                p = f"{rng.choice('ABCDEFGH')}-{rng.randint(10, 99)}"
                if p not in used:
                    used.add(p); break
            for _try in range(100):  # 표지와 라벨이 겹치지 않도록 배치
                near = rng.random() < 0.3  # 경계 근처 배치: 라벨이 경계선과 겹침
                px = x + w - 14 if near else x + rng.uniform(15, w - 80)
                py = y + rng.uniform(25, h - 50)
                if all(abs(py - q["xy"][1]) > 22 or abs(px - q["xy"][0]) > 70 for q in parts.values()):
                    break
            parts[p] = {"zone": z, "xy": (px, py), "near_border": near}
    # 표: 구역마다 단일 값 또는 조건별 두 값
    c2 = rng.sample(CONDS[1:], 1)[0]
    table = {}
    for z in zones:
        base = rng.choice([400, 500, 600, 800])
        if rng.random() < 0.67:
            table[z] = [(base, "*"), (base // 2, "**")]
        else:
            table[z] = [(base, "")]
    foot = {"*": CONDS[0], "**": c2}
    return {"id": f"ZI-{i:03d}", "rev": rng.choice("ABC"), "zones": zones, "zrects": zrects,
            "parts": parts, "table": table, "foot": foot}


def draw_pdf(d, path):
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(70, 790, f"ZONAL INSPECTION REQUIREMENTS   DOC {d['id']}  REV {d['rev']}")
    c.setFont("Helvetica", 9)
    body = ["This section defines the inspection intervals for the zones shown in Figure 1.",
            "Components located within a zone are inspected at the interval of that zone.",
            "Intervals are given in flight hours (FH). Refer to Table 1 for applicable conditions."]
    for k, t in enumerate(body):
        c.drawString(70, 760 - k * 13, t)
    # 그림
    c.setFont("Helvetica-Bold", 9); c.drawString(70, 675, "FIGURE 1. ZONE LOCATION")
    c.setLineWidth(1.2)
    for z, (x, y, w, h) in d["zrects"].items():
        c.rect(x, y, w, h)
        c.setFont("Helvetica-Bold", 10); c.drawString(x + 6, y + h - 16, f"ZONE {z}")
    c.setFont("Helvetica", 8)
    for p, v in d["parts"].items():
        px, py = v["xy"]
        c.rect(px - 3, py - 3, 6, 6, fill=1)
        c.drawString(px + 6, py - 3, p)
    # 표
    ty = 380
    c.setFont("Helvetica-Bold", 9); c.drawString(70, ty + 18, "TABLE 1. ZONAL INSPECTION INTERVALS")
    rows = [("ZONE", "INTERVAL (FH)")] + [(str(z), ", ".join(f"{v}{m}" for v, m in d["table"][z])) for z in d["zones"]]
    rh, cw = 18, (120, 200)
    for r, (a, b) in enumerate(rows):
        yy = ty - r * rh
        c.rect(70, yy - rh + 4, cw[0], rh); c.rect(70 + cw[0], yy - rh + 4, cw[1], rh)
        c.setFont("Helvetica-Bold" if r == 0 else "Helvetica", 9)
        c.drawString(76, yy - 9, a); c.drawString(76 + cw[0], yy - 9, b)
    fyy = ty - len(rows) * rh - 6
    c.setFont("Helvetica", 7)
    used = {m for z in d["zones"] for _, m in d["table"][z] if m}
    k = 0
    for m in ["*", "**"]:
        if m in used:
            c.drawString(72, fyy - k * 10, f"{m} {d['foot'][m]}"); k += 1
    c.setFont("Helvetica", 9)
    c.drawString(70, 230, "Inspection findings shall be recorded in the maintenance record of the aircraft.")
    c.save()


def scan(pdf_path, png_path, rng):
    pdf = pdfium.PdfDocument(str(pdf_path))
    img = pdf[0].render(scale=150 / 72).to_pil().convert("L")
    a = np.array(img).astype(np.float32)
    M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), rng.uniform(-0.6, 0.6), 1.0)
    a = cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), borderValue=255)
    a = cv2.GaussianBlur(a, (3, 3), 0.8)
    a = np.clip(a * 0.92 + 12 + np.random.default_rng(rng.randint(0, 10**6)).normal(0, 9, a.shape), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 55])
    Path(png_path).write_bytes(buf.tobytes())  # 한글 경로에서 cv2.imwrite 실패 회피


def main(n=12, seed=7):
    rng = random.Random(seed)
    OUT.mkdir(exist_ok=True)
    truth, qs = [], []
    for i in range(1, n + 1):
        d = make_doc(i, rng)
        draw_pdf(d, OUT / f"{d['id']}.pdf")
        scan(OUT / f"{d['id']}.pdf", OUT / f"{d['id']}_scan.png", rng)
        t = {"id": d["id"], "parts": {p: v["zone"] for p, v in d["parts"].items()},
             "near_border": [p for p, v in d["parts"].items() if v["near_border"]],
             "table": {str(z): [[v, d["foot"].get(m, "")] for v, m in d["table"][z]] for z in d["zones"]}}
        truth.append(t)
        plist = list(d["parts"])
        rng.shuffle(plist)
        two = [p for p in plist if len(d["table"][d["parts"][p]["zone"]]) == 2]
        one = [p for p in plist if len(d["table"][d["parts"][p]["zone"]]) == 1]
        if two:
            p = two[0]; z = d["parts"][p]["zone"]; (v1, _), (v2, _) = d["table"][z]
            c2 = d["foot"]["**"].rstrip(".").lower()
            qs.append({"doc": d["id"], "type": "조건 지정", "q": f"What is the inspection interval for the zone where {p} is installed, in a {c2}?", "expect": [v2], "forbid": [v1]})
            p = two[-1]; z = d["parts"][p]["zone"]; (v1, _), (v2, _) = d["table"][z]
            qs.append({"doc": d["id"], "type": "조건 미지정", "q": f"What is the inspection interval for the zone where {p} is installed?", "expect": [v1, v2], "forbid": []})
        if one:
            p = one[0]; z = d["parts"][p]["zone"]; v = d["table"][z][0][0]
            qs.append({"doc": d["id"], "type": "단일 기준", "q": f"What is the inspection interval for the zone where {p} is installed?", "expect": [v], "forbid": []})
        p = plist[0]
        qs.append({"doc": d["id"], "type": "기록 없는 조건", "q": f"What is the inspection interval for the zone where {p} is installed, under {rng.choice(ABSENT)}?", "expect": [], "forbid": [], "abstain": True})
    (OUT / "truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")
    (OUT / "questions.json").write_text(json.dumps(qs, indent=1), encoding="utf-8")
    print(len(truth), "docs,", len(qs), "questions")


if __name__ == "__main__":
    main()
