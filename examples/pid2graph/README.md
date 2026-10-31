# PID2Graph 공개 데이터 대조

공개 P&ID 정답 데이터 PID2Graph(독일 항공우주센터, CC BY-SA 4.0, https://zenodo.org/records/14803338)로
래스터 도면 추출(`examples/public-documents/pid/raster_graph.py`)의 배관 연결 재현율을 잰다.
정답은 도면마다 graphml로 제공되며 기호 노드(상자·분류 7종)와 선 간선(실선·점선), 선의 교차·꺾임 노드로 이루어진다.

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
