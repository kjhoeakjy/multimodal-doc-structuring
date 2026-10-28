"""PoC v4: 체결 토크 사례.

실험군
  A 고정 길이 분할: 텍스트(pdftotext 또는 전체 페이지 OCR) → 300토큰 청크 → BM25 상위 3개 입력
  C 제안: 1차 추출(디지털 파서 또는 기본 OCR+도형 검출) → 연결 확인 → 연결 누락 영역 재처리(고해상도 영역 OCR) → 구조화 → 질문에 필요한 관계만 입력
지표: 근거 완전성(입력에 정답 도출에 필요한 정보가 모두 있는 비율), 규칙 판독 정답률, 질의당 입력 토큰, 문서당 처리 시간(CPU), 재처리 영역 수
컨테이너에는 VLM·LLM이 없으므로 재처리는 고해상도 영역 OCR로 대신하고 답변 판독은 규칙으로 함. VLM 재처리와 LLM 판독은 노트북에서 교체 실행.
"""
import json, os, re, sys, time, subprocess
os.environ.setdefault("TIKTOKEN_CACHE_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache"))
from collections import defaultdict
import numpy as np, cv2, pdfplumber, pytesseract, tiktoken, pypdfium2 as pdfium
from PIL import Image, ImageOps
from rank_bm25 import BM25Okapi

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
truth = json.load(open(f"{DATA}/truth.json")); queries = json.load(open(f"{DATA}/queries.json"))
docs = {d["doc"]: d for d in truth["docs"]}
enc = tiktoken.get_encoding("cl100k_base")
ntok = lambda s: len(enc.encode(s))
BASE_DPI, HI_DPI = 130, 300


def render(pdf, dpi):
    return pdfium.PdfDocument(pdf)[0].render(scale=dpi / 72).to_pil().convert("L")


def ocr_words(im):
    d = pytesseract.image_to_data(im, config="--psm 6", output_type=pytesseract.Output.DICT)
    out = []
    for i in range(len(d["text"])):
        t = d["text"][i].strip()
        if t: out.append({"text": t, "x0": d["left"][i], "y0": d["top"][i], "x1": d["left"][i] + d["width"][i], "y1": d["top"][i] + d["height"][i], "line": (d["block_num"][i], d["par_num"][i], d["line_num"][i])})
    return out


def lines_of(words):
    g = defaultdict(list)
    for w in words: g[w["line"]].append(w)
    res = []
    for k in sorted(g, key=lambda k: min(w["y0"] for w in g[k])):
        ws = sorted(g[k], key=lambda w: w["x0"])
        res.append({"text": " ".join(w["text"] for w in ws), "y0": min(w["y0"] for w in ws), "y1": max(w["y1"] for w in ws), "x0": ws[0]["x0"]})
    return res


# ---------- 실험군 A ----------
def plain_text(doc):
    pdf = f"{DATA}/pdf/{doc['doc']}.pdf"
    if not doc["scanned"]:
        return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    return pytesseract.image_to_string(render(pdf, HI_DPI), config="--psm 6")


def chunks(text, size=300, overlap=50):
    ids = enc.encode(text); out = []
    for s in range(0, max(1, len(ids)), size - overlap):
        out.append(enc.decode(ids[s:s + size]))
        if s + size >= len(ids): break
    return out


# ---------- 실험군 C: 1차 추출 ----------
def extract_digital(doc):
    pdf = f"{DATA}/pdf/{doc['doc']}.pdf"
    with pdfplumber.open(pdf) as p:
        pg = p.pages[0]; H = pg.height
        words = [{"text": w["text"], "x0": w["x0"], "y0": w["top"], "x1": w["x1"], "y1": w["bottom"]} for w in pg.extract_words()]
        rects = [(r["x0"], r["top"], r["x1"], r["bottom"]) for r in pg.rects if r["width"] > 60 and r["height"] > 40]
        circles = [((c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2, (c["x1"] - c["x0"]) / 2) for c in pg.curves if 10 < c["x1"] - c["x0"] < 30]
        tables = pg.extract_tables()
    return {"words": words, "rects": rects, "circles": circles, "tables": tables, "unit": "pt", "scale": 1.0}


def extract_scanned(doc):
    pdf = f"{DATA}/pdf/{doc['doc']}.pdf"
    im = render(pdf, BASE_DPI); a = np.asarray(im)
    words = ocr_words(im); ls = lines_of(words)
    # 그림·표 영역: 캡션 행으로 구분
    fig_cap = next((l for l in ls if re.match(r"^FIGURE\s*\d", l["text"].upper())), None)
    tab_cap = next((l for l in ls if re.match(r"^TABLE\s*\d", l["text"].upper())), None)
    fn = next((l for l in ls if l["text"].lstrip().startswith("*")), None)
    fy0, fy1 = (fig_cap["y1"], tab_cap["y0"]) if fig_cap and tab_cap else (0, a.shape[0] // 2)
    # 도형: 부품 상자(큰 사각형), 체결부 원
    th = cv2.threshold(cv2.GaussianBlur(a, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    cnts, _ = cv2.findContours(th, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    rects = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if fy0 < y < fy1 and 150 < w < 450 and 100 < h < 250: rects.append((x, y, x + w, y + h))
    rects = dedupe(rects)
    # 상자 안 부품 번호: 상자 상단 영역 OCR
    for (x0, y0, x1, y1) in rects:
        cr = im.crop((x0 + 2, y0 + 2, x0 + 160, y0 + 34)).resize((316, 64), Image.LANCZOS)
        t = pytesseract.image_to_string(cr, config="--psm 7").strip()
        t = re.sub(r"(?<=[A-Z])l|l(?=[A-Z-])", "I", t.replace("—", "-").replace("_", "-"))   # 식별자 정규화: 소문자 l을 I로
        m = re.search(r"[A-Z]{2}-\d{3}", t)
        if m: words.append({"text": m.group(0), "x0": x0 + 2, "y0": y0 + 2, "x1": x0 + 60, "y1": y0 + 20, "line": ("fig", x0, y0)})
    sub = a[int(fy0):int(fy1)] if fy1 - fy0 > 50 else a
    circ = cv2.HoughCircles(cv2.medianBlur(sub, 3), cv2.HOUGH_GRADIENT, 1, 25, param1=120, param2=18, minRadius=12, maxRadius=22)
    circles = [(float(x), float(y) + fy0, float(r)) for x, y, r in (circ[0] if circ is not None else [])]
    # 표: 캡션과 각주 사이 영역을 따로 OCR
    rows = []
    if tab_cap:
        ty1 = fn["y0"] - 2 if fn else min(a.shape[0], tab_cap["y1"] + 320)
        cr = im.crop((0, tab_cap["y1"] + 2, im.width, ty1))
        rows = table_rows_from_image(cr)
    tables = [[["ITEM", "SIZE", "TORQUE (N·m)"]] + rows]
    return {"words": words, "rects": rects, "circles": circles, "tables": tables, "unit": "px", "scale": BASE_DPI / 72, "lines": ls, "img": im,
            "table_region": (0, tab_cap["y1"] + 2, im.width, ty1) if tab_cap else None}


def table_rows_from_image(cr):
    """격자 표의 셀 단위 OCR: 수평·수직 선을 찾아 셀을 나누고 셀마다 OCR."""
    a = np.asarray(cr); th = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (a.shape[1] // 8, 1)); vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, a.shape[0] // 8))
    hor = cv2.morphologyEx(th, cv2.MORPH_OPEN, hk); ver = cv2.morphologyEx(th, cv2.MORPH_OPEN, vk)
    ys = sorted({int(y) for y in np.where(hor.sum(axis=1) > a.shape[1] * 0.15 * 255)[0]}); xs = sorted({int(x) for x in np.where(ver.sum(axis=0) > a.shape[0] * 0.3 * 255)[0]})
    def merge(v):
        out = []
        for x in v:
            if not out or x - out[-1][-1] > 3: out.append([x])
            else: out[-1].append(x)
        return [int(np.mean(g)) for g in out]
    ys, xs = merge(ys), merge(xs)
    rows = []
    for i in range(len(ys) - 1):
        cells = []
        for j in range(len(xs) - 1):
            c = cr.crop((xs[j] + 3, ys[i] + 3, xs[j + 1] - 3, ys[i + 1] - 3))
            k = 48 / max(1, c.height); c = c.resize((max(1, int(c.width * k)), 48), Image.LANCZOS)   # 셀 높이를 48px로 정규화
            b = cv2.threshold(cv2.GaussianBlur(np.asarray(c), (3, 3), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            cells.append(pytesseract.image_to_string(ImageOps.expand(Image.fromarray(b), border=16, fill=255), config="--psm 7").strip())
        rows.append(cells)
    out = []
    for r in rows:
        if len(r) >= 3 and r[0].strip().isdigit():
            m = re.match(r"(\d+)\s*(\*|\u2022|'|\u201d|\")?", r[2].strip())
            if m: out.append([r[0].strip(), re.sub(r"[^M0-9]", "", r[1].upper()), m.group(1) + (" *" if m.group(2) else "")])
    return out


def dedupe(rs):
    out = []
    for r in rs:
        if not any(abs(r[0] - o[0]) < 8 and abs(r[1] - o[1]) < 8 for o in out): out.append(r)
    return out


def label_in(ext, rect):
    x0, y0, x1, y1 = rect
    ws = [w for w in ext["words"] if x0 <= w["x0"] and w["x1"] <= x1 and y0 <= w["y0"] <= y0 + (y1 - y0) * 0.35]
    for w in ws:
        if re.match(r"^[A-Z]{2}-\d{3}$", w["text"]): return w["text"]
    return None


def callout_digit(ext, cx, cy, r, hi=False, doc=None):
    """원 안의 번호 판독. 디지털은 단어 좌표, 스캔은 영역 OCR(hi=True면 고해상도 재처리)."""
    if ext["unit"] == "pt":
        for w in ext["words"]:
            if abs((w["x0"] + w["x1"]) / 2 - cx) < r and abs((w["y0"] + w["y1"]) / 2 - cy) < r and w["text"].isdigit(): return w["text"]
        return None
    if not hi:
        im = ext["img"]; s = 1
    else:
        im = render(f"{DATA}/pdf/{doc['doc']}.pdf", HI_DPI); s = HI_DPI / BASE_DPI
    f = 0.55
    cr = im.crop((int((cx - r * f) * s), int((cy - r * f) * s), int((cx + r * f) * s), int((cy + r * f) * s)))
    a = cv2.GaussianBlur(np.asarray(cr), (3, 3), 0); th = cv2.threshold(a, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    cr = ImageOps.expand(Image.fromarray(th).resize((90, 90), Image.LANCZOS), border=30, fill=255)
    t = pytesseract.image_to_string(cr, config="--psm 10 -c tessedit_char_whitelist=0123456789").strip()
    return t if t.isdigit() else None


# ---------- 실험군 C: 연결 확인·재처리·구조화 ----------
def structure(doc, ext, stats):
    recs = []; missing = []
    tab = ext["tables"][0] if ext["tables"] else []
    rows = [r for r in tab if r and r[0] and str(r[0]).strip().isdigit()]
    footnote = " ".join(l["text"] for l in (ext.get("lines") or lines_of_pt(ext["words"])) if l["text"].lstrip().startswith("*"))
    lub = dict(re.findall(r"(M\d+)\s+(\d+)\s*N", footnote))
    # 연결 확인(표): 그림의 체결부 수보다 행이 적거나, 각주는 있는데 기호가 붙은 셀이 없으면 표 영역 재처리
    if ext["unit"] == "px" and ext.get("table_region"):
        n_call = len(ext["circles"]); has_mark = any("*" in str(r[2]) for r in rows)
        if len(rows) < n_call or (lub and not has_mark):
            stats["reprocess_regions"] += 1; t = time.time(); stats.setdefault("reasons", []).append("table")
            im = render(f"{DATA}/pdf/{doc['doc']}.pdf", HI_DPI); sc = HI_DPI / BASE_DPI
            x0, y0, x1, y1 = ext["table_region"]
            rows2 = table_rows_from_image(im.crop((int(x0 * sc), int(y0 * sc), int(x1 * sc), int(y1 * sc))))
            if len(rows2) >= len(rows): rows = rows2
            stats["reprocess_sec"] += time.time() - t
    # 표: 셀과 각주 연결
    for r in rows:
        item, size, tq = str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip()
        m = re.match(r"(\d+)\s*(\*?)", tq)
        if not m: continue
        recs.append({"target": f"item {item}", "attr": "size", "value": size, "cond": None, "src": "Table 1 row"})
        recs.append({"target": f"item {item}", "attr": "torque", "value": f"{m.group(1)} N·m", "cond": "dry", "src": "Table 1 row"})
        if size in lub:
            recs.append({"target": f"item {item}", "attr": "torque", "value": f"{lub[size]} N·m", "cond": "lubricated", "src": "Table 1 footnote *"})
        elif m.group(2) == "*" or lub:
            missing.append(("footnote", item, size))
    # 그림: 체결부 원과 부품 상자의 포함 관계
    boxes = [(label_in(ext, rc), rc) for rc in ext["rects"]]
    boxes = [(l, rc) for l, rc in boxes if l]
    found = {}
    reads = []
    for cx, cy, r in ext["circles"]:
        reads.append([callout_digit(ext, cx, cy, r), cx, cy, r])
    seen = [x[0] for x in reads]
    for x in reads:
        if x[0] is None or seen.count(x[0]) > 1:   # 판독 실패 또는 중복 번호: 해당 원에 한해 고해상도 재판독
            stats["reprocess_regions"] += 1; t = time.time(); stats.setdefault("reasons", []).append("callout")
            x[0] = callout_digit(ext, x[1], x[2], x[3], hi=True, doc=doc); stats["reprocess_sec"] += time.time() - t
    for d_, cx, cy, r in reads:
        if d_ is None: continue
        owner = sorted([(abs((x1 - x0) * (y1 - y0)), l) for l, (x0, y0, x1, y1) in boxes if x0 < cx < x1 and y0 < cy < y1])
        if owner and d_ not in found: found[d_] = owner[0][1]   # 가장 안쪽 상자를 소속으로 봄
    for r in rows:
        item = str(r[0]).strip()
        if item in found:
            recs.append({"target": f"item {item}", "attr": "attached to", "value": found[item], "cond": None, "src": "Figure 1 callout"})
        else:
            missing.append(("callout", item, None))
    # 각주 누락 재처리: 표 하단 영역 고해상도 OCR
    if any(m[0] == "footnote" for m in missing) and ext["unit"] == "px":
        stats["reprocess_regions"] += 1; t = time.time()
        tab_lines = ext["lines"]; last = max(tab_lines, key=lambda l: l["y1"])
        im = render(f"{DATA}/pdf/{doc['doc']}.pdf", HI_DPI); s = HI_DPI / BASE_DPI
        y = [l for l in tab_lines if l["text"].lstrip().startswith("*") or "Lubricated" in l["text"]]
        if y:
            l = y[0]; cr = im.crop((0, int((l["y0"] - 4) * s), im.width, int((l["y1"] + 4) * s)))
            fn2 = pytesseract.image_to_string(cr, config="--psm 7")
            lub2 = dict(re.findall(r"(M\d+)\s+(\d+)\s*N", fn2))
            for kind, item, size in list(missing):
                if kind == "footnote" and size in lub2:
                    recs.append({"target": f"item {item}", "attr": "torque", "value": f"{lub2[size]} N·m", "cond": "lubricated", "src": "Table 1 footnote * (reprocessed)"})
                    missing.remove((kind, item, size))
        stats["reprocess_sec"] += time.time() - t
    return recs, missing


def lines_of_pt(words):
    g = defaultdict(list)
    for w in words: g[round(w["y0"] / 4)].append(w)
    return [{"text": " ".join(x["text"] for x in sorted(v, key=lambda w: w["x0"])), "y0": k * 4, "y1": k * 4 + 10} for k, v in sorted(g.items())]


# ---------- 질의 ----------
def parse_q(q):
    cond = "lubricated" if "lubricated" in q["question"] else ("dry" if q["type"] == "value" else None)
    return q.get("item"), q.get("part"), cond


def compose_input(q, recs):
    item, part, cond = parse_q(q)
    if part and item is None:
        att = [r for r in recs if r["attr"] == "attached to" and r["value"] == part]
        targets = [r["target"] for r in att]
    elif part:
        att = [r for r in recs if r["attr"] == "attached to" and r["value"] == part]
        targets = [r["target"] for r in att]
    else:
        targets = [f"item {item}"]; att = []
    sel = att + [r for r in recs if r["target"] in targets and r["attr"] in ("size", "torque") and (cond is None or r["cond"] in (None, cond))]
    lines = [f"{r['target']} | {r['attr']} | {r['value']} | {r['cond'] or '-'} | {r['src']}" for r in sel]
    return "target | attribute | value | condition | source\n" + "\n".join(lines), sel


def judge_c(q, sel):
    """규칙 판독: 구조화 입력에서 답을 읽음. 정답 여부와 근거 완전성."""
    item, part, cond = parse_q(q)
    tq = [r for r in sel if r["attr"] == "torque"]
    if q["type"] == "unspecified":
        vals = sorted(int(r["value"].split()[0]) for r in tq)
        return vals == sorted(q["answer"])
    vals = [int(r["value"].split()[0]) for r in tq if r["cond"] == cond]
    return len(vals) == 1 and vals[0] == q["answer"]


def judge_a(q, ctx, doc):
    """고정 길이 분할 입력의 근거 완전성: 필요한 사실이 모두 문맥에 있는가(관대한 기준)."""
    item, part, cond = parse_q(q)
    f = next(x for x in docs[doc]["items"] if x["item"] == (item or q["item"]))
    t = re.sub(r"\s+", " ", ctx)
    row_ok = re.search(rf"\b{f['item']}\s+{f['size']}\s+{f['dry']}\b", t) is not None
    fn_ok = re.search(rf"{f['size']}\s+{f['lub']}\s*N", t) is not None
    link_ok = False  # 체결부와 부품의 소속 관계는 텍스트에 없음(그림 정보)
    if q["type"] == "value": return row_ok
    if q["type"] == "condition": return row_ok and fn_ok
    return row_ok and fn_ok and link_ok


def flatten(ext, recs):
    """실험군 B: 제안과 같은 1차 추출·재처리 결과를 평문으로 펼침(관계 연결 없음). 구조화 효과만 분리해 비교."""
    lines = []
    if ext["unit"] == "pt":
        lines += [l["text"] for l in lines_of_pt(ext["words"])]
    else:
        lines += [l["text"] for l in ext["lines"]]
    tab = ext["tables"][0] if ext["tables"] else []
    lines += [" ".join(str(c) for c in r) for r in tab]
    fig = [w["text"] for w in ext["words"] if w.get("line", ("",))[0] == "fig"]
    lines += fig
    # 체결부 번호는 그림 텍스트로만 존재(소속 관계 없음)
    lines += [r["target"].replace("item ", "callout ") for r in recs if r["attr"] == "attached to"]
    return "\n".join(lines)


def main():
    out = {"docs": {}, "queries": []}
    recs_by_doc = {}; ctx_by_doc = {}; ctxB_by_doc = {}
    for d in truth["docs"]:
        st = {"reprocess_regions": 0, "reprocess_sec": 0.0}
        t = time.time(); txt = plain_text(d); st["A_sec"] = time.time() - t
        ctx_by_doc[d["doc"]] = chunks(txt)
        t = time.time(); ext = extract_digital(d) if not d["scanned"] else extract_scanned(d); st["C_extract_sec"] = time.time() - t
        t = time.time(); recs, missing = structure(d, ext, st); st["C_structure_sec"] = time.time() - t
        st["missing_after"] = missing; st["n_records"] = len(recs); st["scanned"] = d["scanned"]
        recs_by_doc[d["doc"]] = recs; out["docs"][d["doc"]] = st
        ctxB_by_doc[d["doc"]] = chunks(flatten(ext, recs))
    for q in queries:
        d = q["doc"]
        ch = ctx_by_doc[d]; bm = BM25Okapi([c.lower().split() for c in ch])
        top = bm.get_top_n(q["question"].lower().split(), ch, n=3)
        ctxA = "\n---\n".join(top)
        chB = ctxB_by_doc[d]; bmB = BM25Okapi([c.lower().split() for c in chB])
        ctxB = "\n---\n".join(bmB.get_top_n(q["question"].lower().split(), chB, n=3))
        inpC, sel = compose_input(q, recs_by_doc[d])
        out["queries"].append({"type": q["type"], "doc": d, "scanned": docs[d]["scanned"],
                               "A_tokens": ntok(ctxA), "A_ok": judge_a(q, ctxA, d),
                               "B_tokens": ntok(ctxB), "B_ok": judge_a(q, ctxB, d),
                               "C_tokens": ntok(inpC), "C_ok": judge_c(q, sel), "C_input": inpC})
    json.dump(out, open(f"{DATA}/results.json", "w"), indent=1, ensure_ascii=False)
    # 요약
    import statistics as S
    print("| 질의 유형 | 건수 | A 근거 완전성 | B 근거 완전성 | C 규칙 정답률 | A 토큰 | B 토큰 | C 토큰 |"); print("|---|---|---|---|---|---|---|---|")
    for ty in ["value", "condition", "figure", "unspecified"]:
        qs = [x for x in out["queries"] if x["type"] == ty]
        print(f"| {ty} | {len(qs)} | {sum(x['A_ok'] for x in qs)/len(qs):.0%} | {sum(x['B_ok'] for x in qs)/len(qs):.0%} | {sum(x['C_ok'] for x in qs)/len(qs):.0%} | {S.median(x['A_tokens'] for x in qs):.0f} | {S.median(x['B_tokens'] for x in qs):.0f} | {S.median(x['C_tokens'] for x in qs):.0f} |")
    for sc in [False, True]:
        qs = [x for x in out["queries"] if x["scanned"] == sc]
        print(f"{'스캔본' if sc else '디지털'}: A {sum(x['A_ok'] for x in qs)/len(qs):.0%}, B {sum(x['B_ok'] for x in qs)/len(qs):.0%}, C {sum(x['C_ok'] for x in qs)/len(qs):.0%}, n={len(qs)}")
    ds = out["docs"]
    for sc in [False, True]:
        dd = [v for v in ds.values() if v["scanned"] == sc]
        print(f"{'스캔본' if sc else '디지털'} 문서당 처리 시간(초): A 전체 페이지 {S.mean(v['A_sec'] for v in dd):.2f}, C 1차 추출 {S.mean(v['C_extract_sec'] for v in dd):.2f} + 구조화 {S.mean(v['C_structure_sec'] for v in dd):.2f} (재처리 영역 평균 {S.mean(v['reprocess_regions'] for v in dd):.1f}개, {S.mean(v['reprocess_sec'] for v in dd):.2f}초), 미해결 연결 평균 {S.mean(len(v['missing_after']) for v in dd):.1f}")


if __name__ == "__main__":
    main()
