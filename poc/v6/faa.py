"""풀 1: FAA AC 43.13-1B Table 7-1(체결 토크 표) 구조화.
값 하나마다 나사 계열, 너트 종류, 하중 조건, 주의문 조건, 각주를 연결함."""
import re, sys, time
from pathlib import Path
import numpy as np, cv2, pdfplumber, pypdfium2 as pdfium

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw" / "faa_ac43-13-1b_ch7.pdf"
PAGE = 4
DPI = 200
S = DPI / 72
_ocr = None


def render(scan=False, seed=3):
    img = np.array(pdfium.PdfDocument(str(RAW))[PAGE].render(scale=S).to_pil().convert("L")).astype(np.float32)
    if scan:
        rng = np.random.default_rng(seed)
        M = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), 0.4, 1.0)
        img = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderValue=255)
        img = cv2.GaussianBlur(img, (3, 3), 0.9)
        img = np.clip(img * 0.9 + 15 + rng.normal(0, 10, img.shape), 0, 255)
        ok, buf = cv2.imencode(".jpg", img.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 50])
        img = cv2.imdecode(buf, 0).astype(np.float32)
    return img.astype(np.uint8)


def deskew(img):
    """긴 가로선의 기울기로 스캔 각도를 추정해 보정함."""
    bw = (img < 150).astype(np.uint8) * 255
    lines = cv2.HoughLinesP(bw, 1, np.pi / 1800, 300, minLineLength=img.shape[1] // 3, maxLineGap=10)
    if lines is None:
        return img
    ang = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4)]
    ang = [a for a in ang if abs(a) < 5]
    if not ang:
        return img
    a = float(np.median(ang))
    M = cv2.getRotationMatrix2D((img.shape[1] / 2, img.shape[0] / 2), a, 1.0)
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderValue=255)


def fix_pn(t):
    """부품 번호(AN, MS)의 숫자 자리 O를 0으로 보정."""
    return re.sub(r"\b(AN|MS)([0-9O]+)\b", lambda m: m.group(1) + m.group(2).replace("O", "0"), t)



def norm_val(v):
    """OCR 혼동 보정: 값 끝의 큰따옴표는 각주 기호, 천 단위 마침표는 쉼표."""
    v = re.sub(r"[\"']+\*?$", "*", v)
    v = re.sub(r"(\d)\.(\d{3})\b", r"\1,\2", v)
    v = re.sub(r"-[.,]", "-", v)
    return v.replace("O", "0") if re.fullmatch(r"[\dO,\-*]+", v) else v


# ---------- 1차 추출 ----------
def first_pass(scan=False):
    t = time.time()
    if not scan:
        with pdfplumber.open(RAW) as pdf:
            pg = pdf.pages[PAGE]
            ws = pg.extract_words(x_tolerance=1.5)
            words = [{"text": w["text"], "box": (w["x0"] * S, w["top"] * S, w["x1"] * S, w["bottom"] * S)} for w in ws]
            vl = [((r["x0"] + r["x1"]) / 2 * S, r["top"] * S, r["bottom"] * S) for r in pg.rects if r["width"] < 2 and r["height"] > 6]
            hl = [(r["top"] * S, r["x0"] * S, r["x1"] * S) for r in pg.rects if r["height"] < 2 and r["width"] > 30]
        img = None
    else:
        global _ocr
        import easyocr
        if _ocr is None:
            _ocr = easyocr.Reader(["en"], gpu=False, verbose=False)
        img = deskew(render(scan=True))
        words = []
        for b, txt, c in _ocr.readtext(img, width_ths=0.3):
            xs, ys = [p[0] for p in b], [p[1] for p in b]
            for k, part in enumerate(txt.split()):  # 단어 단위 근사 분할
                n = len(txt.split()); w = (max(xs) - min(xs)) / n
                words.append({"text": part, "box": (min(xs) + k * w, min(ys), min(xs) + (k + 1) * w, max(ys)), "conf": c})
        bw = (img < 150).astype(np.uint8)
        v = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25)))
        h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1)))
        vl, hl = [], []
        for c in cv2.findContours(v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, hh = cv2.boundingRect(c); vl.append((x + w / 2, y, y + hh))
        for c in cv2.findContours(h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, w, hh = cv2.boundingRect(c); hl.append((y + hh / 2, x, x + w))
    return {"words": words, "vl": vl, "hl": hl, "img": img, "scan": scan, "sec": time.time() - t}


# ---------- 구조화 ----------
SIZE_RE = re.compile(r"^(\d+-\d+|\d/\d+-\d+|\d+/\d+-\d+|1-\d/\d-\d+|1-1/\d-\d+|1-\d+)$")
VAL_RE = re.compile(r"^[\d,]+(?:-[\d,]+)?\*?$")


def lines_of(words, tol=8):
    ws = sorted(words, key=lambda w: (w["box"][1] + w["box"][3]) / 2)
    out = []
    for w in ws:
        cy = (w["box"][1] + w["box"][3]) / 2
        if out and abs(out[-1]["cy"] - cy) < tol:
            out[-1]["ws"].append(w)
        else:
            out.append({"cy": cy, "ws": [w]})
    for l in out:
        l["ws"].sort(key=lambda w: w["box"][0])
        l["text"] = " ".join(w["text"] for w in l["ws"])
    return out


def cells_at(fp, y, x0, x1):
    """y 높이를 가로지르는 세로선으로 x0~x1 구간을 칸으로 나눔."""
    xs = sorted({round(v[0]) for v in fp["vl"] if v[1] - 3 <= y <= v[2] + 3 and x0 - 5 <= v[0] <= x1 + 5})
    merged = []
    for x in xs:
        if not merged or x - merged[-1] > 10:
            merged.append(x)
    return list(zip(merged[:-1], merged[1:]))


def structure(fp):
    L = lines_of(fp["words"])
    gaps = []
    up = lambda s: s.upper()
    cau = [l for l in L if up(l["text"]).startswith("CAUTION")]
    i_c = L.index(cau[0]) if cau else 0
    caution = L[i_c + 1]["text"] if cau else ""
    sizes = [l for l in L if l["ws"] and SIZE_RE.match(l["ws"][0]["text"].replace(" ", ""))]
    if not sizes:
        return {"facts": [], "gaps": [{"type": "데이터 행 없음"}]}
    # 표 범위는 표 테두리 가로선 기준(데이터 행 위아래 가로선의 최소, 최대 x)
    ys = (sizes[0]["cy"] - 300, sizes[-1]["cy"] + 300)
    tl = [h for h in fp["hl"] if ys[0] < h[0] < ys[1]]
    tx0 = min(h[1] for h in tl) - 3 if tl else min(w["box"][0] for l in sizes for w in l["ws"]) - 15
    tx1 = max(h[2] for h in tl) + 3 if tl else max(w["box"][2] for l in sizes for w in l["ws"]) + 40
    y_data = sizes[0]["cy"]
    cols = cells_at(fp, y_data, tx0, tx1)
    if len(cols) != 5:
        gaps.append({"type": f"표 세로선 {len(cols)}칸 검출(5칸 예상)"})
    # 머리글: 주의문 아래와 첫 데이터 행 위 사이 줄
    head_lines = [l for l in L if (cau and l["cy"] > L[i_c + 1]["cy"] + 5 or not cau) and l["cy"] < y_data - 5 and "SERIES" not in up(l["text"])]
    head = {k: [] for k in range(len(cols))}
    for l in head_lines:
        cs = cells_at(fp, l["cy"], tx0, tx1)
        for cx0, cx1 in cs:
            txt = " ".join(w["text"] for w in l["ws"] if cx0 <= (w["box"][0] + w["box"][2]) / 2 <= cx1)
            if not txt:
                continue
            for k, (c0, c1) in enumerate(cols):
                if min(c1, cx1) - max(c0, cx0) > 0.5 * (c1 - c0):  # 열 폭의 절반 이상 겹치면 해당 머리글 적용
                    head[k].append(txt)
    headers = {k: fix_pn(re.sub(r"-\s+", "", " ".join(v))) for k, v in head.items()}
    for k, h in headers.items():
        if not h:
            gaps.append({"type": "머리글 없는 열", "col": k})
    # 계열 구분 줄과 각주
    series = [(l["cy"], l["text"]) for l in L if "THREAD SERIES" in up(l["text"])]
    foot = {}
    for l in L:
        m = re.match(r"^\*\s*(.+)", l["text"])
        if m:
            foot["*"] = m.group(1)
    scope = " ".join(l["text"] for l in L if "may be used for all" in l["text"] or "approximately equal number" in l["text"])
    facts = []
    for l in sizes:
        sz = l["ws"][0]["text"]
        ser = [t for y, t in series if y < l["cy"]]
        ser = ser[-1].title() if ser else ""
        if not ser:
            gaps.append({"type": "행의 나사 계열 미확인", "row": sz})
        cells = {}
        for w in l["ws"][1:]:
            cx = (w["box"][0] + w["box"][2]) / 2
            for k, (c0, c1) in enumerate(cols):
                if c0 <= cx <= c1:
                    cells.setdefault(k, []).append(w["text"])
        vals = {k: norm_val("".join(v)) for k, v in cells.items() if k > 0}
        if len(vals) != len(cols) - 1:
            gaps.append({"type": "행의 값 개수 불일치", "row": sz, "cy": l["cy"], "got": len(vals)})
        for k, v in vals.items():
            if not VAL_RE.match(v):
                gaps.append({"type": "값 형식 이상", "row": sz, "val": v, "cy": l["cy"]})
            star = v.endswith("*")
            if star and "*" not in foot:
                gaps.append({"type": "각주 기호에 대응하는 각주 없음"})
            facts.append({"col": k, "대상": f"{sz} bolt", "속성": headers.get(k, f"col{k}"), "값": v.rstrip("*") + " in-lb",
                          "조건": "; ".join(c for c in [ser, caution, "estimated value" if star else ""] if c),
                          "출처": f"Table 7-1, row {sz}, column {k + 1}" + (", footnote *" if star else "") + ", caution"})
    return {"facts": facts, "gaps": gaps, "headers": headers, "caution": caution, "foot": foot, "scope": scope, "cols": cols}


def repair(fp, st):
    """연결 누락에 한해 원본 영역을 소형 VLM으로 재해석: 각주 미연결은 표 하단, 값 이상은 해당 행."""
    log = []
    if not fp["scan"]:
        return log
    sys.path.insert(0, str(ROOT.parent / "v5"))
    import vlm
    x0, x1 = int(st["cols"][0][0]), int(st["cols"][-1][1])
    if any(g["type"].startswith("각주") for g in st["gaps"]):
        yb = int(max(h[0] for h in fp["hl"]))
        crop = fp["img"][yb - 70:yb + 10, x0:x1]
        lines, dt, n, _ = vlm.read_region(crop, max_new_tokens=64)
        txt = " ".join(lines)
        m = re.search(r"Estimated[^.]*\.?", txt, re.I)
        if m:
            st["foot"]["*"] = m.group(0)
        log.append({"gap": "각주", "sec": round(dt, 1), "tokens": n, "text": txt[:120]})
    for g in [g for g in st["gaps"] if g["type"] == "값 형식 이상"]:
        y = int(g["cy"])
        crop = fp["img"][y - 14:y + 14, int(st["cols"][1][0]):x1]
        lines, dt, n, _ = vlm.read_region(crop, max_new_tokens=40)
        toks = [norm_val(t) for t in " ".join(lines).split()]
        toks = [t for t in toks if VAL_RE.match(t)]
        fixed = None
        if len(toks) == len(st["cols"]) - 1:
            for f in st["facts"]:
                if f["대상"] == f"{g['row']} bolt":
                    v = toks[f["col"] - 1]
                    f["값"] = v.rstrip("*") + " in-lb"
            fixed = toks
        log.append({"gap": "값 형식", "row": g["row"], "sec": round(dt, 1), "tokens": n, "result": fixed})
    if st["foot"].get("*"):
        for f in st["facts"]:
            if "footnote *" in f["출처"] and "estimated" not in f["조건"]:
                f["조건"] += "; estimated value"
    return log
