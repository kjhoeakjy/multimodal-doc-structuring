"""풀 2: NIST 시험 도면의 일반 주기 구조화.
주기마다 적용 범위(UNLESS OTHERWISE SPECIFIED, APPLIES TO ...)를 연결하고,
텍스트 레이어에 없는 기하공차 기호는 연결 누락으로 판단해 해당 영역만 재해석함."""
import re, sys, time
from pathlib import Path
import numpy as np, pdfplumber, pypdfium2 as pdfium

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
DPI = 200
S = DPI / 72
FCF_RE = re.compile(r"^(\d+)\.\s*([\d\s.]*\d)\s+((?:[A-Z]\s){1,3})APPLIES TO (.+)$")


def first_pass(doc):
    t = time.time()
    with pdfplumber.open(RAW / f"nist-{doc}.pdf") as pdf:
        pg = pdf.pages[0]
        words = pg.extract_words(x_tolerance=1.5, keep_blank_chars=False)
        curves = [c for c in pg.curves] + [l for l in pg.lines]
        H = pg.height
    # 세로 중심이 겹치는 단어를 한 줄로 묶음(공차 기입 틀 안 글자는 기준선이 조금 다름)
    lines = []
    for w in sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"])):
        cy = (w["top"] + w["bottom"]) / 2
        tgt = next((l for l in lines if abs(l["cy"] - cy) < 4 and (w["x0"] - l["x1"] < 60 and l["x0"] - w["x1"] < 60)), None)
        if tgt:
            tgt["ws"].append(w); tgt["x0"] = min(tgt["x0"], w["x0"]); tgt["x1"] = max(tgt["x1"], w["x1"])
            tgt["top"] = min(tgt["top"], w["top"]); tgt["bottom"] = max(tgt["bottom"], w["bottom"])
        else:
            lines.append({"cy": cy, "ws": [w], "x0": w["x0"], "x1": w["x1"], "top": w["top"], "bottom": w["bottom"]})
    for l in lines:
        l["text"] = " ".join(w["text"] for w in sorted(l["ws"], key=lambda w: w["x0"]))
    lines.sort(key=lambda l: (round(l["top"]), l["x0"]))
    return {"doc": doc, "lines": lines, "curves": curves, "sec": time.time() - t}


def structure(fp):
    L = fp["lines"]
    i0 = next((i for i, l in enumerate(L) if l["text"].startswith("NOTES")), None)
    gaps, notes = [], {}
    if i0 is None:
        return {"notes": notes, "gaps": [{"type": "주기 영역 없음"}], "facts": []}
    head = L[i0]
    x_lim = head["x0"] + 300
    cur = None
    for l in L[i0 + 1:]:
        if l["x0"] > x_lim:
            continue
        m = re.match(r"^(\d+)\.\s*(.*)", l["text"])
        if m and l["x0"] < head["x0"] + 20:
            cur = m.group(1); notes[cur] = {"text": m.group(2), "box": [l["x0"], l["top"], l["x1"], l["bottom"]]}
        elif cur:
            notes[cur]["text"] += " " + l["text"]; notes[cur]["box"][3] = l["bottom"]
    facts = []
    for n, v in notes.items():
        t = re.sub(r"-\s+", "-", v["text"])
        fm = FCF_RE.match(f"{n}. {t}")
        if fm:
            tol = re.sub(r"\s", "", fm.group(2)); dat = fm.group(3).split()
            v["fcf"] = {"tol": tol, "datums": dat, "applies": fm.group(4), "symbol": None}
            gaps.append({"type": "기하공차 기호 미확인", "note": n, "box": v["box"]})
        facts.append({"대상": fp["doc"].upper(), "속성": f"note {n}", "값": t, "조건": "UNLESS OTHERWISE SPECIFIED (drawing general notes)", "출처": f"{fp['doc'].upper()} page 1 note {n}"})
    return {"notes": notes, "gaps": gaps, "facts": facts}


def classify_symbol_vector(fp, box):
    """PDF 벡터 객체로 기호 판별: 공차 칸 안 곡선(호)과 밑변 직선이 있으면 면의 윤곽도."""
    x0, y0 = box[0] + 8, box[1] - 4
    cand = [c for c in fp["curves"] if x0 - 2 <= c["x0"] and c["x1"] <= x0 + 30 and y0 - 2 <= c["top"] and c["bottom"] <= y0 + 18]
    arcs = [c for c in cand if len(c.get("pts", [])) > 4 or c.get("object_type") == "curve"]
    base = [c for c in cand if c.get("object_type") == "line" and abs(c["top"] - c["bottom"]) < 0.5]
    if arcs:
        return "profile of a surface" if base or len(cand) > 1 else "profile of a line"
    return None


def render_crop(doc, box, pad=6):
    img = np.array(pdfium.PdfDocument(str(RAW / f"nist-{doc}.pdf"))[0].render(scale=S).to_pil().convert("L"))
    x0, y0, x1, y1 = [int(v * S) for v in box]
    return img[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]


def repair(fp, st, use_vlm=True):
    log = []
    for g in st["gaps"]:
        if g["type"] != "기하공차 기호 미확인":
            continue
        n = g["note"]; v = st["notes"][n]
        t = time.time()
        sym = classify_symbol_vector(fp, v["box"])
        how = "벡터 객체"
        if sym is None and use_vlm:
            sys.path.insert(0, str(ROOT.parent / "v5"))
            import vlm
            lines, dt, ntok, raw = vlm.read_region(render_crop(fp["doc"], [v["box"][0], v["box"][1], v["box"][0] + 120, v["box"][1] + 14]), max_new_tokens=32)
            joined = " ".join(lines).lower()
            sym = "profile of a surface" if "⌓" in raw or "profile" in joined else None
            how = "VLM"
        v["fcf"]["symbol"] = sym
        if sym:
            f = v["fcf"]
            for fa in st["facts"]:
                if fa["속성"] == f"note {n}":
                    fa["값"] = f"{sym} tolerance {f['tol']} relative to datums {' '.join(f['datums'])} applies to {f['applies']}"
        log.append({"note": n, "how": how, "symbol": sym, "sec": round(time.time() - t, 2)})
    return log
