"""풀 2(NIST 시험 도면) 비교 실행. 방식 구분은 run_faa.py와 동일."""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent / "v5"))
import nist, qa
from rank_bm25 import BM25Okapi

D = ROOT / "data"
QS = json.loads((ROOT / "questions_nist.json").read_text(encoding="utf-8"))
DOCS = sorted({q["doc"] for q in QS})
SYS = ("Answer the question using only the context from the engineering drawing. Quote tolerance type, value and datums when asked. "
       "If the context does not contain the requested information, answer 'Not specified.'")


def prep():
    out = D / "nist_prep.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    import pdfplumber, pypdfium2 as pdfium
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, VlmPipelineOptions
    from docling.datamodel import vlm_model_specs
    from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.pipeline.vlm_pipeline import VlmPipeline
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=PdfPipelineOptions(do_ocr=False, do_table_structure=True), backend=PyPdfiumDocumentBackend)})
    spec = vlm_model_specs.GRANITEDOCLING_TRANSFORMERS.model_copy(update={"max_new_tokens": 3000})
    vconv = DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_cls=VlmPipeline, pipeline_options=VlmPipelineOptions(vlm_options=spec))})
    res = {"time": {"A": 0, "C": 0, "S": 0, "B": 0}, "docs": {}}
    for d in DOCS:
        r = {}
        img = D / f"nist-{d}.png"
        pdfium.PdfDocument(str(nist.RAW / f"nist-{d}.pdf"))[0].render(scale=nist.S).to_pil().save(img)
        t = time.time(); fp = nist.first_pass(d); st = nist.structure(fp); r["gaps"] = [g["type"] for g in st["gaps"]]
        r["repair"] = nist.repair(fp, st, use_vlm=False); r["facts"] = st["facts"]; dt = time.time() - t
        res["time"]["C"] += dt
        t = time.time()
        with pdfplumber.open(nist.RAW / f"nist-{d}.pdf") as pdf:
            r["A_text"] = pdf.pages[0].extract_text()
        res["time"]["A"] += time.time() - t
        t = time.time(); r["S_md"] = conv.convert(str(nist.RAW / f"nist-{d}.pdf"), page_range=(1, 1)).document.export_to_markdown(image_placeholder=""); res["time"]["S"] += time.time() - t
        t = time.time(); r["B_md"] = vconv.convert(str(img)).document.export_to_markdown(image_placeholder=""); res["time"]["B"] += time.time() - t
        res["docs"][d] = r
        print(d, {k: round(v, 1) for k, v in res["time"].items()}); sys.stdout.flush()
    res["time"] = {k: round(v / len(DOCS), 1) for k, v in res["time"].items()}  # 도면당 평균
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


TERMS = ["untoleranced", "units", "square brackets", "material", "restrain", "free state", "y14.41"]


def packet(facts, q):
    tk = lambda s: re.findall(r"[a-z0-9.]+", s.lower())
    bm = BM25Okapi([tk(f["값"]) for f in facts])
    sc = bm.get_scores(tk(q))
    top = sorted(range(len(facts)), key=lambda i: -sc[i])[:2]
    sel = [facts[i] for i in top]
    need = [t for t in TERMS if t in q.lower()]
    lines = [f"- {f['출처']}: {f['값']} (scope: {f['조건']})" for f in sel]
    if need and not any(t in " ".join(f["값"].lower() for f in sel) for t in need):
        lines.append(f"- No general note in this drawing addresses: {', '.join(need)}.")
    return "\n".join(lines)


def judge(ans, qd):
    a = ans.lower().replace("0.0", ".0").replace(" 0.", " .")
    if qd.get("abstain"):
        return any(k in a for k in ("not specified", "no general note", "not provided", "does not"))
    return all(k in a for k in qd["kw"])


def run(methods):
    P = prep()
    res = []
    for qd in QS:
        r0 = P["docs"][qd["doc"]]
        for m in methods:
            if m == "E":
                import e2e
                ans, ntok, sec = e2e.ask(D / f"nist-{qd['doc']}.png", SYS, qd["q"]); ctx = "(page image)"
            else:
                ctx = {"A": lambda: qa.bm25_ctx(r0["A_text"], qd["q"]), "S": lambda: qa.bm25_ctx(r0["S_md"], qd["q"]),
                       "B": lambda: qa.bm25_ctx(r0["B_md"], qd["q"]), "C": lambda: packet(r0["facts"], qd["q"])}[m]()
                ans, ntok, sec = qa.ask(ctx, qd["q"], sys_prompt=SYS)
            r = {"pool": "nist", "method": m, "doc": qd["doc"], "type": qd["type"], "q": qd["q"], "ok": judge(ans, qd), "in_tokens": ntok, "sec": round(sec, 1), "ans": ans, "ctx": ctx}
            res.append(r); print(json.dumps({k: r[k] for k in ("method", "doc", "type", "ok", "in_tokens", "sec", "ans")}, ensure_ascii=False)); sys.stdout.flush()
    (D / f"qa_nist_{''.join(methods)}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    run(list(sys.argv[1]))
