# PID2Graph 공개 데이터 대조

공개 P&ID 정답 데이터 PID2Graph(독일 항공우주센터, CC BY-SA 4.0, https://zenodo.org/records/14803338)로
래스터 도면 추출(`examples/public-documents/pid/raster_graph.py`)의 배관 연결 재현율을 잰다.
정답은 도면마다 graphml로 제공되며 기호 노드(상자·분류)와 선 간선, 선의 교차·꺾임 노드로 이루어진다.

2026-11-03 확인(노트북 C:\data\PID2Graph, 13.45 GB): Complete 폴더에 Dataset PID 500장(png+graphml), PID2Graph Synthetic 250장, OPEN100 완전 도면 12장(1994×1330~3342×2222 px, 도면당 노드 181~675). 노드 속성은 label·xmin·ymin·xmax·ymax, 간선 속성은 edge_label(12장 모두 solid). 기호 종류는 connector·crossing·arrow·instrumentation·valve·general·inlet/outlet·background·tank·pump. 문자 속성은 없으나 영상의 태그 문자(장비·계기·밸브·노즐·라인 사양)는 선명해 반자동 주석(OCR 제안 + 사람 확인)으로 질의응답 정답을 만들 수 있음.

## 절차

1. `gt_from_graphml.py` — graphml의 기호가 아닌 노드를 통과시켜 기호 간 인접 쌍을 만든다. 경로에 점선이 있으면 신호선.
2. `run_all.py` — PNG마다 OCR, 해상도 추정(파일 메타데이터 또는 문자 상자 높이·용지 규격), 관계 그래프 추출, 대조.
3. `evaluate.py` — 정답 기호를 상자 겹침으로 추출 노드에 대응시키고 배관 정답 쌍의 복원 비율(재현율)과 정답 밖 쌍 비율(정밀도)을 적는다.

```
python examples/pid2graph/run_all.py <PID2Graph 폴더> examples/pid2graph/output --filter OPEN100
```

데이터 원본은 저장소에 넣지 않는다. 표본과 결과 표만 `output/`에 둔다.

## 기준의 차이

- 기존 공개 P&ID(DEXPI) 대조는 장비·노즐·배관 부품을 단위로 하고 정답이 설계 파일에서 나온다. 이 데이터는 기호 상자를 단위로 하며 문자 주석이 없어 라벨 대응은 재지 않는다.
- 추출 결과의 작은 표식(mark)과 화살표는 대응 후보에서 제외한다. 정답 기호 둘이 한 추출 노드에 대응되면 '병합'으로 따로 센다.

## 태그 반자동 주석(`annotate_tags.py`)

graphml에 문자 정답이 없어, 기호 상자마다 OCR 제안 태그를 적은 CSV를 만들고 사람이 `확정 태그` 열을 채운다.

- 계기 원: 원을 4배 확대해 PaddleOCR(PP-OCRv5)로 읽음(`paddle_crops.py`). 5번 도면 계기 32개 모두 정확 일치, 글자가 가장 작은 4번 도면은 12개 중 6개. 끝이 `8`이면 `B 후보` 열에 B로 바꾼 값을 적음(자동 치환 안 함).
- 밸브·장비: 상자 3배 영역을 0°/90°/270° 회전해 EasyOCR로 읽고 태그 모양 문자만 고름. 숫자 자리 I·L→1, O→0 정규화. 한 도면에서 반복되는 밸브 태그(예: `V-1-100X` 자리표시)는 `중복` 표시.
- `자동 신뢰`: 계기 원 높이 중앙값 45 px 이상 도면(8, 5, 9, 6, 7번)의 계기 원 OCR은 `높음`, 나머지는 `확인 필요`.

PaddleOCR은 프로젝트 가상환경과 의존성이 겹치지 않도록 별도 가상환경에 설치한다.

```
python -m venv C:\data\ocr-venv
C:\data\ocr-venv\Scripts\python.exe -m pip install paddlepaddle paddleocr opencv-python-headless
python examples/pid2graph/annotate_tags.py "<PID2Graph>/Complete/PID2Graph OPEN100" C:/data/PID2Graph/annotations --only 6,5,7,9,8,11,10,0,1,3,2,4
```

CPU의 Paddle 3.x는 oneDNN 경로에서 `ConvertPirAttribute2RuntimeAttribute not support` 오류가 나므로 `enable_mkldnn=False`와 환경 변수 `FLAGS_use_mkldnn=0`으로 끈다(`paddle_crops.py`에 넣어 둠). 첫 실행 때 OCR 모델을 내려받는다.
