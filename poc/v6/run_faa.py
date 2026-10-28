"""풀 1(FAA Table 7-1) 비교 실행.
A 고정 길이 분할 텍스트 검색 / S Docling 기본 파이프라인 / B Granite-Docling 페이지 전체 변환 / E 페이지 이미지 직접 입력 / C 제안."""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent / "v5"))
import faa, qa

D = ROOT / "data"
QS = json.loads((ROOT / "questions_faa.json").read_text(encoding="utf-8"))
COND_TERMS = ["lubricat", "anti-seize", "oil", "grease", "zinc", "wet", "dry film"]


def prep(mode):
    """전처리 결과를 만들고 처리 시간을 기록함(재사용)."""
    out = D / f"faa_{mode}_prep.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    res = {"mode": mode, "time": {}}
    scan = mode == "scan"
    img_path = D / f"faa_{mode}.png"
    import cv2
    img = faa.render(scan=scan)
    img_path.write_bytes(cv2.imencode(".png", img)[1].tobytes())
    # 제안: 1차 추출, 관계 점검, 선택적 재분석, 구조화
    t = time.time(); fp = faa.first_pass(scan); st = faa.structure(fp); gaps = [g["type"] for g in st["gaps"]]
    log = faa.repair(fp, st); res["time"]["C"] = round(time.time() - t, 1)
    res["C_facts"] = st["facts"]; res["C_gaps"] = gaps; res["C_repair"] = log
    res["A_text"] = "\n".join(l["text"] for l in faa.lines_of(fp["words"]))
    res["time"]["A"] = round(fp["sec"], 1)
    # Docling 기본 파이프라인
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    po = PdfPipelineOptions(do_ocr=scan, ocr_options=EasyOcrOptions(lang=["en"], use_gpu=False), do_table_structure=True)
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=po, backend=PyPdfiumDocumentBackend),
                                             InputFormat.IMAGE: ImageFormatOption(pipeline_options=po)})
    t = time.time()
    r = conv.convert(str(faa.RAW), page_range=(faa.PAGE + 1, faa.PAGE + 1)) if not scan else conv.convert(str(img_path))
    res["time"]["S"] = round(time.time() - t, 1); res["S_md"] = r.document.export_to_markdown(image_placeholder="")
    # Granite-Docling 페이지 전체 변환
    from docling.datamodel.pipeline_options import VlmPipelineOptions
    from docling.datamodel import vlm_model_specs
    from docling.pipeline.vlm_pipeline import VlmPipeline
    spec = vlm_model_specs.GRANITEDOCLING_TRANSFORMERS.model_copy(update={"max_new_tokens": 3000})
    vconv = DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(pipeline_cls=VlmPipeline, pipeline_options=VlmPipelineOptions(vlm_options=spec))})
    t = time.time(); r = vconv.convert(str(img_path))
    res["time"]["B"] = round(time.time() - t, 1); res["B_md"] = r.document.export_to_markdown(image_placeholder="")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def packet(facts, q):
    m = re.search(r"\b(\d+-\d+/\d+-\d+|\d+/\d+-\d+|\d+-\d+)\b bolt", q)
    size = m.group(1) if m else None
    rows = [f for f in facts if f["대상"] == f"{size} bolt"]
    if not rows:
        return f"No row for {size} bolt in Table 7-1."
    maxq = "maximum" in q.lower()
    nut = re.search(r"\b(MS20365|MS20364|AN310|AN320)\b", q)
    sel = [f for f in rows if (("MAXIMUM" in f["속성"]) == maxq)]
    if nut:
        sel = [f for f in sel if nut.group(1) in f["속성"]]
    lines = []
    for f in sel:
        lines.append(f"- {f['대상']}, {f['속성']}: {f['값']}. Conditions: {f['조건']}. (source: {f['출처']})")
    asked = [t for t in COND_TERMS if t in q.lower() and t not in " ".join(f["조건"].lower() for f in sel).replace("oil free", "")]
    if asked:
        lines.append(f"- The table values apply only to oil-free cadmium-plated threads. No value is given for the requested thread condition ({', '.join(asked)}).")
    return "\n".join(lines)


def judge(ans, qd):
    a = ans.lower().replace(",", "")
    nums = {int(n) for n in re.findall(r"\b(\d{1,5})\b", a)}
    if qd.get("abstain"):
        return any(k in a for k in ("not specified", "not given", "no value", "not provided", "does not", "only to oil", "oil-free", "oil free"))
    ok = set(qd["expect"]) <= nums and not (set(qd["forbid"]) & nums)
    if qd.get("keyword"):
        ok = ok and qd["keyword"] in a
    return ok


def run(mode, methods):
    P = prep(mode)
    res = []
    for qd in QS:
        for m in methods:
            if m == "E":
                import e2e
                ans, ntok, sec = e2e.ask(D / f"faa_{mode}.png", qa.SYS.replace("inspection interval in flight hours (FH)", "torque value"), qd["q"])
                ctx = "(page image)"
            else:
                if m == "A": ctx = qa.bm25_ctx(P["A_text"], qd["q"])
                elif m == "S": ctx = qa.bm25_ctx(P["S_md"], qd["q"])
                elif m == "B": ctx = qa.bm25_ctx(P["B_md"], qd["q"])
                else: ctx = packet(P["C_facts"], qd["q"])
                ans, ntok, sec = qa.ask(ctx, qd["q"], sys_prompt=SYS)
            r = {"pool": "faa", "mode": mode, "method": m, "type": qd["type"], "q": qd["q"], "ok": judge(ans, qd), "in_tokens": ntok, "sec": round(sec, 1), "ans": ans, "ctx": ctx}
            res.append(r); print(json.dumps({k: r[k] for k in ("mode", "method", "type", "ok", "in_tokens", "sec", "ans")}, ensure_ascii=False)); sys.stdout.flush()
    (D / f"qa_faa_{mode}_{''.join(methods)}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


SYS = ("Answer the question using only the context. Give torque values in inch-pounds. "
       "If the question does not specify the nut type, list the value for each nut type. "
       "State if a value is estimated. If the context does not give a value for the requested condition, answer 'Not specified.'")

if __name__ == "__main__":
    run(sys.argv[1], list(sys.argv[2]))
