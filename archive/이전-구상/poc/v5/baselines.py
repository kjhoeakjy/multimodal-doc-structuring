"""비교 대상의 전처리 실행.
std   Docling 기본 파이프라인(레이아웃, 표 구조, EasyOCR)으로 마크다운 변환
fullvlm  Granite-Docling으로 페이지 전체 변환
결과 마크다운과 처리 시간을 data/에 저장함."""
import json, sys, time
from pathlib import Path

D = Path(__file__).parent / "data"


def run_std(ids, mode):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    po = PdfPipelineOptions(do_ocr=(mode == "scan"), ocr_options=EasyOcrOptions(lang=["en"], use_gpu=False), do_table_structure=True)
    conv = DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=po, backend=PyPdfiumDocumentBackend),
        InputFormat.IMAGE: ImageFormatOption(pipeline_options=po)})
    log = {}
    for did in ids:
        src = D / (f"{did}.pdf" if mode == "digital" else f"{did}_scan.png")
        t = time.time(); r = conv.convert(str(src)); dt = time.time() - t
        md = r.document.export_to_markdown(image_placeholder="")
        (D / f"{did}_{mode}_std.md").write_text(md, encoding="utf-8")
        log[did] = round(dt, 1); print(did, mode, "std", log[did], "s", len(md)); sys.stdout.flush()
    (D / f"time_std_{mode}.json").write_text(json.dumps(log), encoding="utf-8")


def run_fullvlm(ids, max_new_tokens=1200):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmPipelineOptions
    from docling.datamodel import vlm_model_specs
    from docling.document_converter import DocumentConverter, ImageFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    spec = vlm_model_specs.GRANITEDOCLING_TRANSFORMERS.model_copy(update={"max_new_tokens": max_new_tokens})
    conv = DocumentConverter(format_options={InputFormat.IMAGE: ImageFormatOption(
        pipeline_cls=VlmPipeline, pipeline_options=VlmPipelineOptions(vlm_options=spec))})
    log = {}
    for did in ids:
        t = time.time(); r = conv.convert(str(D / f"{did}_scan.png")); dt = time.time() - t
        md = r.document.export_to_markdown(image_placeholder="")
        (D / f"{did}_scan_fullvlm.md").write_text(md, encoding="utf-8")
        log[did] = round(dt, 1); print(did, "fullvlm", log[did], "s", len(md)); sys.stdout.flush()
        (D / "time_fullvlm.json").write_text(json.dumps(log), encoding="utf-8")


if __name__ == "__main__":
    what, mode = sys.argv[1], sys.argv[2]
    ids = sys.argv[3].split(",") if len(sys.argv) > 3 else [f"ZI-{i:03d}" for i in range(1, 13)]
    run_std(ids, mode) if what == "std" else run_fullvlm(ids)
