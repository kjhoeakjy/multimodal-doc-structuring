"""실험군 A~D 실행 및 평가.

A. 기본: 전체 쪽 OCR -> 고정 길이 텍스트 청크 -> BM25 상위 k
B. 통합 모델: 전 문서 문서 VLM -> Markdown 청크 -> BM25 상위 k
C. 구조화: 문서 VLM -> 정보 단위 -> 질문별 Evidence Packet
D. 제안: 직접 파싱(디지털) + 문서 VLM(스캔본) + 검증 -> 정보 단위 -> Evidence Packet

사용: python pipeline.py data [--arms A,B,C,D] [--llm model.gguf] [--k 3]
문서 VLM은 docling(granite_docling)을 사용하며, 결과는 data/cache 에 저장해 재사용함.
"""
import argparse, glob, json, os, re, shutil, sqlite3, subprocess, sys, time
from collections import Counter, defaultdict

import numpy as np
import pdfplumber
from rank_bm25 import BM25Okapi

ap = argparse.ArgumentParser()
ap.add_argument("data"); ap.add_argument("--arms", default="A,B,C,D"); ap.add_argument("--llm", default=None)
ap.add_argument("--k", type=int, default=3); ap.add_argument("--chunk", type=int, default=400)
args = ap.parse_args()
D = args.data; ARMS = args.arms.split(","); K = args.k
CACHE = f"{D}/cache"; os.makedirs(CACHE, exist_ok=True)
truth = json.load(open(f"{D}/truth.json")); queries = json.load(open(f"{D}/queries.json"))
DOCS = {d["doc"]: d for d in truth["docs"]}
ID_RE = re.compile(r"^[A-Z]{2}-\d{3}$")
ATTR = {"TEMPERATURE": "max_temperature", "PRESSURE": "max_pressure"}
COND = {"NORMAL": "normal", "EMERG": "emergency"}

# ---------- 공통 ----------
def render(pdf, dpi):
    import pypdfium2 as pdfium
    return pdfium.PdfDocument(pdf)[0].render(scale=dpi / 72).to_pil().convert("L")

def count_tokens(s):
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(s))
    except Exception:
        return max(1, len(s) // 4)

def tok(s): return re.findall(r"[A-Za-z]+|\d+", s.lower())

def fix_id(s):
    m = re.match(r"^([A-Z]{2})-?0?(\d{3})$", s.strip().upper().replace(" ", "").replace("—", "-").replace("–", "-"))
    return f"{m.group(1)}-{m.group(2)}" if m else s.strip()

def norm_unit(h):
    h = h.upper().replace(" ", "")
    if "KPA" in h: return "kPa"
    if "PSI" in h: return "psi"
    if re.search(r"[°º*o]?C\)", h) or "°C" in h: return "°C"
    return None

# OCR 백엔드: tesseract 우선, 없으면 easyocr
_OCR = None
def ocr_text(img, psm=3):
    global _OCR
    if _OCR is None:
        try:
            import pytesseract; pytesseract.get_tesseract_version(); _OCR = ("tess", pytesseract)
        except Exception:
            import easyocr; _OCR = ("easy", easyocr.Reader(["en"], gpu=False, verbose=False))
    if _OCR[0] == "tess":
        return _OCR[1].image_to_string(img, config=f"--psm {psm}")
    res = _OCR[1].readtext(np.asarray(img), detail=1, paragraph=False)
    res.sort(key=lambda r: (round(r[0][0][1] / 15), r[0][0][0]))
    lines, cur, y0 = [], [], None
    for box, t, _ in res:
        y = box[0][1]
        if y0 is not None and abs(y - y0) > 15: lines.append(" ".join(cur)); cur = []
        cur.append(t); y0 = y
    lines.append(" ".join(cur)); return "\n".join(lines)

def ocr_page_cached(doc):
    p = f"{CACHE}/{doc}_ocr.txt"
    if not os.path.exists(p):
        open(p, "w", encoding="utf-8").write(ocr_text(render(f"{D}/pdf/{doc}.pdf", 150)))
    return open(p, encoding="utf-8").read()

def chunks(doc, text, size, ov=80):
    out, i = [], 0
    while i < len(text): out.append((doc, text[i:i + size])); i += size - ov
    return out

# ---------- 문서 VLM(docling) ----------
def vlm_convert(doc):
    """docling granite_docling 변환. 반환: {"markdown": str, "tables": [grid], "text": str}"""
    p = f"{CACHE}/{doc}_vlm.json"
    if os.path.exists(p): return json.load(open(p, encoding="utf-8"))
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmPipelineOptions
    from docling.datamodel import vlm_model_specs
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    opts = VlmPipelineOptions(vlm_options=vlm_model_specs.GRANITEDOCLING_TRANSFORMERS)
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=opts)})
    t0 = time.time(); res = conv.convert(f"{D}/pdf/{doc}.pdf"); dt = time.time() - t0
    dd = res.document
    tables = []
    for t in dd.tables:
        g = t.data.grid
        tables.append([[c.text for c in row] for row in g])
    out = {"markdown": dd.export_to_markdown(), "tables": tables, "text": dd.export_to_text(), "seconds": dt}
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out

# ---------- 직접 파싱(디지털 PDF) ----------
def grid_from_cells(cells):
    def merge(v, tol=6):
        out = []
        for a in sorted(v):
            if not out or a - out[-1] > tol: out.append(a)
        return out
    xs = merge(set(round(c[0]) for c in cells) | set(round(c[2]) for c in cells))
    ys = merge(set(round(c[1]) for c in cells) | set(round(c[3]) for c in cells))
    near = lambda v, arr: min(range(len(arr)), key=lambda i: abs(arr[i] - v))
    G = [[""] * (len(xs) - 1) for _ in range(len(ys) - 1)]
    for x0, y0, x1, y1, t in cells:
        for r in range(near(y0, ys), near(y1, ys)):
            for c in range(near(x0, xs), near(x1, xs)): G[r][c] = t
    return G

def parse_digital(doc):
    page = pdfplumber.open(f"{D}/pdf/{doc}.pdf").pages[0]
    if len(page.chars) < 50: return None
    text = page.extract_text() or ""
    t = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    tables = []
    for tb in t:
        cells = [(c[0], c[1], c[2], c[3], (page.within_bbox(c).extract_text() or "").replace("\n", " ")) for c in tb.cells]
        tables.append(grid_from_cells(cells))
    return {"text": text, "tables": tables}

# ---------- 구조화: 정보 단위 ----------
def table_to_units(G, doc, config, source):
    """2단 헤더 + 본문. 병합 셀은 격자 채움으로 보존. 헤더 경로(상위 헤더/하위 헤더)를 Parent Context로 둠."""
    units = []
    if len(G) < 3: return units
    h1, h2 = G[0], G[1]
    # 병합된 상위 헤더가 빈 칸으로 들어온 경우 왼쪽 값으로 채움
    for i in range(1, len(h1)):
        if not (h1[i] or "").strip() and i >= 2: h1[i] = h1[i - 1]
    group = ""
    for ri in range(2, len(G)):
        row = G[ri]
        if (row[0] or "").strip(): group = row[0].strip()
        target = fix_id(row[1] or "")
        for ci in range(2, len(row)):
            top, sub = (h1[ci] or ""), (h2[ci] or "")
            attr = next((v for k, v in ATTR.items() if k in top.upper()), None)
            cond = next((v for k, v in COND.items() if k in sub.upper()), None)
            raw = (row[ci] or "").strip().replace(",", "")
            try: val = float(raw)
            except ValueError: val = None
            units.append({"subject": target, "attribute": attr, "qualifier": cond, "config": config, "group": group,
                          "value": val, "raw": raw, "unit": norm_unit(top),
                          "parent": {"doc": doc, "table": "TABLE 1 OPERATING LIMITS", "header": [top.strip(), sub.strip()]},
                          "provenance": {"doc": doc, "page": 1, "table": 1, "row": ri, "col": ci, "source": source},
                          "status": "extracted"})
    return units

def clause_units(text, doc):
    out = []
    m = re.search(r"apply to Configuration\s+([A-Z])", text or "")
    config = m.group(1) if m else None
    m2 = re.search(r"Emergency limits are short-duration values \(([^)]*)\)", text or "")
    if m2: out.append({"subject": doc, "attribute": "emergency_limit_duration", "qualifier": None, "config": config, "value": None,
                       "raw": m2.group(1), "unit": None, "parent": {"doc": doc, "section": "2. APPLICABILITY"},
                       "provenance": {"doc": doc, "page": 1, "section": 2, "source": "text"}, "status": "extracted"})
    return config, out

# ---------- 검증(D) ----------
def verify(units, doc, ocr_table_text):
    idx = defaultdict(dict)
    for u in units:
        if u["value"] is not None and u["attribute"] and u["qualifier"]:
            idx[(u["subject"], u["attribute"])][u["qualifier"]] = u["value"]
    for u in units:
        if u["attribute"] == "emergency_limit_duration": u["status"] = "verified"; continue
        why = []
        if u["value"] is None or u["unit"] not in ("°C", "kPa", "psi") or not u["attribute"] or not u["qualifier"] or not ID_RE.match(u["subject"] or "") or not u["config"]:
            why.append("format")
        else:
            pair = idx.get((u["subject"], u["attribute"]), {})
            n, e = pair.get("normal"), pair.get("emergency")
            if n is not None and e is not None and e < n: why.append("relation:emergency<normal")
            lo, hi = {"°C": (-60, 400), "kPa": (100, 50000), "psi": (15, 7500)}[u["unit"]]
            if not (lo <= u["value"] <= hi): why.append("relation:range")
            # 원본 근거: 추출값 문자열이 원본 표 영역의 독립 판독 결과에 존재하는지
            if u["provenance"]["source"] == "vlm" and ocr_table_text is not None:
                if not re.search(rf"(?<!\d){int(u['value'])}(?!\d)", ocr_table_text): why.append("source")
        u["checks"] = why
        u["status"] = "verified" if not why else "review"
    return units

# ---------- 저장(DB) 및 Evidence Packet ----------
def build_db(units):
    db = sqlite3.connect(":memory:")
    db.execute("create table u(doc, subject, attribute, qualifier, config, grp, value, raw, unit, status, prov, parent)")
    db.executemany("insert into u values(?,?,?,?,?,?,?,?,?,?,?,?)",
                   [(u["provenance"]["doc"], u["subject"], u["attribute"], u["qualifier"], u["config"], u.get("group"), u["value"], u["raw"], u["unit"], u["status"],
                     json.dumps(u["provenance"]), json.dumps(u["parent"])) for u in units])
    return db

def fmt_unit(r):
    doc, subj, attr, qual, cfg, grp, val, raw, unit, status, prov, parent = r
    pv = json.loads(prov); pa = json.loads(parent)
    loc = f"{pv['doc']} p.{pv['page']}" + (f" table {pv['table']} r{pv['row']} c{pv['col']}" if "table" in pv else f" section {pv.get('section')}")
    ctx = f"{pa.get('table', pa.get('section'))}" + (f" > {' / '.join(h for h in pa['header'] if h)}" if "header" in pa else "")
    v = f"{raw} {unit}" if unit else raw
    return f"[{ctx}] {subj} {attr} ({qual or '-'}; Configuration {cfg}; group {grp or '-'}) = {v} | status={status} | source={loc}"

def packet(db, q):
    """질문 유형별 최소 충분 근거. 미확정 단위가 포함되면 hold 표시."""
    rows = []
    if q["type"] == "lookup":
        rows = db.execute("select * from u where subject=? and attribute=? and qualifier=? and config=?", (q["target"], q["attr"], q["cond"], q["config"])).fetchall()
    elif q["type"] == "compare":
        rows = db.execute("select * from u where subject in (?,?) and attribute=? and qualifier=? and config=?", (q["target"], q["target2"], q["attr"], q["cond"], q["config"])).fetchall()
    elif q["type"] == "explain":
        rows = db.execute("select * from u where attribute='emergency_limit_duration' and config=? and doc=?", (q["config"], q["doc"])).fetchall()
    elif q["type"] == "membership":
        rows = db.execute("select * from u where subject=? and config=? limit 1", (q["target"], q["config"])).fetchall()
    if not rows: return "", "none"
    hold = any(r[9] == "review" for r in rows)
    head = f"Applicability: values apply to Configuration {q['config']} only."
    return head + "\n" + "\n".join(fmt_unit(r) for r in rows), ("hold" if hold else "ok")

# ---------- 평가 ----------
def judge_context(ctx, q):
    """근거 포함·오염 판정(LLM 없이)."""
    other = "B" if q["config"] == "A" else "A"
    if q["type"] == "lookup":
        hit = (re.search(rf"(?<!\d){q['value']}(?!\d)", ctx) is not None) and (q["target"] in ctx.replace(" ", ""))
        of = [f for f in truth["facts"] if f["target"] == q["target"] and f["attr"] == q["attr"] and f["cond"] == q["cond"] and f["config"] == other]
        contam = bool(of) and re.search(rf"(?<!\d){of[0]['value']}(?!\d)", ctx) is not None and f"Configuration {other}" in ctx
        return hit, contam
    if q["type"] == "compare":
        return (q["target"] in ctx and q["target2"] in ctx and f"Configuration {q['config']}" in ctx), (f"Configuration {other}" in ctx)
    if q["type"] == "explain":
        return ("60 s" in ctx or "60s" in ctx), False
    if q["type"] == "membership":
        return (q["answer"] in ctx and q["target"] in ctx and f"Configuration {q['config']}" in ctx), (f"Configuration {other}" in ctx)

_LLM = None
def llm_answer(ctx, q):
    global _LLM
    if _LLM is None:
        from llama_cpp import Llama
        _LLM = Llama(model_path=args.llm, n_ctx=4096, verbose=False)
    prompt = ("Answer using only the context. Reply with the value and unit, a component ID, a group name, or a duration. If the context is insufficient or marked hold, reply INSUFFICIENT.\n\n"
              f"Context:\n{ctx}\n\nQuestion: {q['question']}\nAnswer:")
    out = _LLM(prompt, max_tokens=24, temperature=0)["choices"][0]["text"].strip()
    return out

def score_answer(ans, q):
    a = ans.replace(",", "")
    if q["type"] == "lookup": return re.search(rf"(?<!\d){q['value']}(?!\d)", a) is not None
    if q["type"] == "compare": return q["answer"] in a and (q["target2"] if q["answer"] == q["target"] else q["target"]) not in a
    if q["type"] == "explain": return "60" in a
    if q["type"] == "membership": return q["answer"] in a.upper()

# ---------- 실행 ----------
results, prep = {}, {}
docs = sorted(DOCS)

def run_chunk_arm(name, texts):
    CH = [c for d, t in texts.items() for c in chunks(d, t, args.chunk)]
    bm = BM25Okapi([tok(c[1]) for c in CH])
    per = []
    for q in queries:
        sc = bm.get_scores(tok(q["question"])); top = np.argsort(sc)[::-1][:K]
        ctx = "\n---\n".join(f"[{CH[i][0]}]\n{CH[i][1]}" for i in top)
        hit, contam = judge_context(ctx, q)
        rec = {"q": q["question"], "type": q["type"], "hit": hit, "contam": contam, "tokens": count_tokens(ctx), "status": "ok", "ctx": ctx}
        if args.llm: rec["answer"] = llm_answer(ctx, q); rec["correct"] = score_answer(rec["answer"], q)
        per.append(rec)
    results[name] = per

def run_packet_arm(name, units):
    db = build_db(units); per = []
    for q in queries:
        ctx, st = packet(db, q)
        hit, contam = judge_context(ctx, q) if ctx else (False, False)
        rec = {"q": q["question"], "type": q["type"], "hit": hit, "contam": contam, "tokens": count_tokens(ctx), "status": st, "ctx": ctx}
        if args.llm:
            rec["answer"] = "INSUFFICIENT" if st != "ok" else llm_answer(ctx, q); rec["correct"] = score_answer(rec["answer"], q) if st == "ok" else False
        per.append(rec)
    results[name] = per

if "A" in ARMS:
    t0 = time.time(); texts = {d: ocr_page_cached(d) for d in docs}; prep["A"] = {"seconds": time.time() - t0, "vlm_pages": 0, "ocr_pages": len(docs)}
    run_chunk_arm("A", texts)

if "B" in ARMS or "C" in ARMS or "D" in ARMS:
    need = docs if ("B" in ARMS or "C" in ARMS) else [d for d in docs if DOCS[d]["scanned"]]
    vlm = {}
    t0 = time.time()
    for d in need:
        try: vlm[d] = vlm_convert(d)
        except Exception as e:
            print(f"[VLM 실패] {d}: {e}", file=sys.stderr); vlm = None; break
    t_vlm_all = time.time() - t0

if "B" in ARMS and vlm is not None:
    prep["B"] = {"seconds": sum(vlm[d].get("seconds", 0) for d in docs), "vlm_pages": len(docs), "ocr_pages": 0}
    run_chunk_arm("B", {d: vlm[d]["markdown"] for d in docs})

def units_from(doc, src, source):
    config, cu = clause_units(src["text"], doc)
    us = []
    for G in src["tables"]: us += table_to_units(G, doc, config, source)
    return us + cu

if "C" in ARMS and vlm is not None:
    t0 = time.time(); U = []
    for d in docs: U += units_from(d, vlm[d], "vlm")
    prep["C"] = {"seconds": prep.get("B", {}).get("seconds", sum(vlm[d].get("seconds", 0) for d in docs)) + time.time() - t0, "vlm_pages": len(docs), "ocr_pages": 0, "units": len(U)}
    run_packet_arm("C", U)

if "D" in ARMS and vlm is not None:
    t0 = time.time(); U = []; stat = Counter()
    for d in docs:
        dig = parse_digital(d)
        if dig is not None:
            us = units_from(d, dig, "parser"); stat["parser"] += 1; ocr_tbl = None
        else:
            us = units_from(d, vlm[d], "vlm"); stat["vlm"] += 1
            ocr_tbl = ocr_page_cached(d)   # 독립 판독(원본 근거 검증용)
        U += verify(us, d, ocr_tbl)
    prep["D"] = {"seconds": sum(vlm[d].get("seconds", 0) for d in docs if DOCS[d]["scanned"]) + time.time() - t0, "vlm_pages": stat["vlm"], "parser_pages": stat["parser"], "units": len(U),
                 "verified": sum(u["status"] == "verified" for u in U), "review": sum(u["status"] == "review" for u in U)}
    # 정보 단위 정확도
    F = {(f["doc"], f["target"], f["attr"], f["cond"]): f for f in truth["facts"]}
    ok = tot = 0; rev_wrong = 0
    for u in U:
        f = F.get((u["provenance"]["doc"], u["subject"], u["attribute"], u["qualifier"]))
        if u["attribute"] == "emergency_limit_duration": continue
        tot += 1; c = bool(f and u["value"] is not None and abs(u["value"] - f["value"]) < 1e-9 and u["unit"] == f["unit"] and u["config"] == f["config"]); ok += c
        if u["status"] == "review" and not c: rev_wrong += 1
    prep["D"]["unit_accuracy"] = ok / max(1, tot); prep["D"]["review_actual_error"] = rev_wrong
    run_packet_arm("D", U)

# ---------- 집계 ----------
summary = {}
for name, per in results.items():
    n = len(per); s = {"n": n, "근거 포함률": sum(r["hit"] for r in per) / n, "다른 조건 오염률": sum(r["contam"] for r in per) / n,
                       "질의당 토큰": sum(r["tokens"] for r in per) / n, "보류": sum(r["status"] == "hold" for r in per), "미조회": sum(r["status"] == "none" for r in per)}
    if args.llm: s["QA 정답률"] = sum(r.get("correct", False) for r in per) / n
    for t in ["lookup", "compare", "explain", "membership"]:
        sub = [r for r in per if r["type"] == t]
        s[f"{t} 근거 포함률"] = sum(r["hit"] for r in sub) / max(1, len(sub))
    summary[name] = s
out = {"전처리": prep, "질의 평가": summary}
json.dump(out, open(f"{D}/results.json", "w"), ensure_ascii=False, indent=1)
json.dump({k: [{kk: vv for kk, vv in r.items()} for r in v] for k, v in results.items()}, open(f"{D}/results_detail.json", "w"), ensure_ascii=False, indent=0)

# Before/After 사례: A에서 다른 조건 문서에 오염된 조회 질의 1건과 D의 Packet
if "A" in results and "D" in results:
    for ra, rd in zip(results["A"], results["D"]):
        if ra["type"] == "lookup" and ra["contam"] and rd["hit"] and rd["status"] == "ok":
            open(f"{D}/before_after.md", "w", encoding="utf-8").write(
                f"# Before/After\n\n질문: {ra['q']}\n\n## A. OCR 텍스트 청크 (토큰 {ra['tokens']})\n```\n{ra['ctx']}\n```\n\n## D. 정보 단위 Evidence Packet (토큰 {rd['tokens']})\n```\n{rd['ctx']}\n```\n")
            break
print(json.dumps(out, ensure_ascii=False, indent=1))
