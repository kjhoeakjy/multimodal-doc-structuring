# 질의응답 정답률 실험

구조화 결과가 텍스트 전용 LLM의 답에 얼마나 도움이 되는지 잰다. 같은 문서에 대해 세 가지 입력 조건으로 같은 질문을 하고 정답률을 비교함.

| 조건 | 입력 | 뜻 |
|---|---|---|
| `ocr` | 문자 인식 결과(벡터는 SVG 문자)를 읽는 순서로 이어 붙인 텍스트 | 구조화 없는 기준선 |
| `full` | 전체 직렬화(`graph.txt`·`page.txt`: 요소·연결·표·문단·관계) | 문서 한 장을 통째로 투입 |
| `retrieved` | 질문 태그 기준 2단계 부분 그래프와 질문어가 겹치는 줄(표 머리글 포함) | 검색 후 투입(RAG) |

## 자료와 정답

| 자료 | 문항 | 정답 출처 |
|---|---|---|
| DEXPI C01 P&ID: 벡터, 200 dpi 래스터, 스캔 열화 | 43 × 3 | DEXPI XML(연결·노즐 수·노즐 호칭 지름·라인 속성·계기 기능 문자) |
| DEXPI C02·C03 P&ID 벡터 | 12 | DEXPI XML |
| 합성 보고서(영문 PDF 글자 층·150 dpi 스캔), 한글 보고서, 한글 표·본문 스캔 | 35 | 생성 스크립트의 값 |
| 합성 기계 도면(벡터·래스터) | 20 | 생성 스크립트의 값 |
| FAA AC 43.13-1B 토크 표(원본·스캔), 볼트 표, 본문 2단 쪽 | 44 | 원문 대조 값 |

연결 질문은 "장비 X에서 배관을 따라 다른 장비를 거치지 않고 바로 도달하는 장비 태그"이며 정답은 XML 연결 정보에서 이름 없는 부품(밸브 등)을 지나 탐색해 만든 집합임. 채점은 단일 답은 정규화 후 포함 여부, 집합 답은 응답에서 뽑은 태그 집합의 완전 일치.

## 실행

```
python prepare_docs.py          # C02·C03 벡터 도면 처리(표본 결과는 examples/sample-inputs/output 사용)
python make_questions.py        # questions.json
python contexts.py              # contexts.json(세 조건 문맥)
python run_qa.py --backend anthropic --model <모델 id>      # 키는 환경 변수 ANTHROPIC_API_KEY
python run_qa.py --backend ollama --model <모델 이름>        # 공개 가중치 모델, 로컬 Ollama
```

결과는 `results/<모델>.jsonl`(문항·조건별 응답)과 `results/<모델>.md`(자료별·질문 종류별 정답률, 입력 길이, 응답 시간). 중단 후 다시 실행하면 남은 문항만 호출함.
