# PoC v3: 선택적 전처리 및 의미·관계 보존형 구조화

v4 수정안 7.1 비교 실험의 구현.

## 구성

| 파일 | 내용 |
|---|---|
| `gen.py` | 합성 기술문서 20건(디지털 10, 스캔본 10) 생성. 적용 조건 조항, 2단 헤더·병합 셀 표, 부품 배치 그림. 정답 사실 480건, 질의 198건(조회·비교·설명·소속) |
| `pipeline.py` | 실험군 A~D 실행, 근거 포함률·다른 조건 오염률·질의당 토큰·보류 집계, Before/After 사례 추출 |

## 실험군

| 실험군 | 전처리 | 구조화 및 LLM 입력 |
|---|---|---|
| A | 전체 쪽 OCR | 고정 길이 청크, BM25 상위 k |
| B | 전 문서 문서 VLM(docling granite_docling) | Markdown 청크, BM25 상위 k |
| C | 문서 VLM | 정보 단위(Subject·Attribute·Qualifier·Value/Unit·Parent·Provenance·Status) + Evidence Packet |
| D | 직접 파싱(디지털) + 문서 VLM(스캔본) + 형식·관계·원본 근거 검증 | 정보 단위 + Evidence Packet, 미확정 시 보류 |

## 실행

```
pip install docling pdfplumber rank_bm25 pypdfium2 tiktoken pillow numpy pytesseract
python gen.py data
python pipeline.py data --arms A,B,C,D [--llm model.gguf]
```

- OCR 백엔드: tesseract(설치 필요). 없으면 easyocr 사용.
- `--llm`에 GGUF 모델을 주면 llama-cpp-python으로 QA 정답률을 함께 측정함. 없으면 근거 포함률·오염률·토큰만 측정함.
- 문서 VLM 결과는 `data/cache`에 저장되어 재실행 시 재사용됨.
- `data/`는 생성물이므로 커밋하지 않음. 결과는 `data/results.json`, `data/before_after.md`.

## 한계

- 합성 데이터 기반 통제 실험. 오류 유형(적용 조건 혼동, 스캔 잡음)은 생성 시 설계한 것이며 실데이터 성능이 아님.
- 근거 포함률은 문자열 대조로 판정하므로 LLM 정답률의 상한에 해당함.
