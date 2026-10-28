# PoC 목록

구상안 버전에 대응하는 실험 코드. 생성 데이터(`data/`)와 캐시는 커밋하지 않음.

| 경로 | 대응 구상안 | 사례 | 데이터 | 상태 |
|---|---|---|---|---|
| `v4/` | v10 | 체결 토크(조립도 체결부 소속, 토크 표, 윤활 각주) | 합성 20건(디지털 10, 스캔 10) | 1차 실행 완료. 실험군 A 고정 분할, B 평문 분할, D 요소 단위 분할, E 페이지 전체 입력, C 제안 |
| `v5/` | v10 | 구역별 점검 주기 | 합성 12건 | 노트북에서 실행 후 정리 예정 |
| `v6/` | v10 이후 | 제조 문서 세 풀(FAA AC 43.13-1B 7장, NIST 시험 도면, 부품 도해 목록 합성) | 공개 원본 2종과 합성 1종 | 노트북에서 진행 중 |
| `archive/v3-information-unit/` | v4 수정안 | 정보 단위와 근거 묶음 | 합성 20건 | 대체됨 |
| `archive/v2-evidence-unit-draft/` | v2 | 공통 정보 단위 | 초안 | 미완성, 대체됨 |
| `archive/v1-revision-check/` | v1 | 개정과 적용 조건 검증 | 합성 부품 30종, 검사 기록 600건 | 실행 결과 포함, 대체됨 |

## 공통 구성

- `gen.py`: 합성 문서 생성과 정답 기록(`truth.json`, `queries.json`)
- `pipeline.py`: 실험군 실행과 지표 집계(`results.json`)
- `README.md`: 실험군, 지표, 결과, 확인된 한계

## 실행 환경

- 공통: Python 3, reportlab, pypdfium2, pdfplumber, pytesseract(tesseract 설치), opencv-python, rank_bm25, tiktoken, numpy, pillow
- 노트북 전용: docling, Granite-Docling, 소형 로컬 LLM. 컨테이너에는 VLM과 LLM이 없어 추가 분석은 고해상도 영역 OCR, 답변 판독은 규칙으로 대체함
