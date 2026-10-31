# 정답 대조 결과

정답 인접 쌍 6개 중 3개 복원 (재현율 0.50), 두 요소가 한 노드로 합쳐진 쌍 2개. 그림에 기호가 없는 요소 3개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 2개는 통과 처리. 추출 인접 쌍 17개 중 정답에 없는 쌍 14개. 이 중 4개는 계측 신호선 연결로 배관 정답의 범위 밖이고 10개는 오류임. 배관 쌍 기준 정밀도 0.23.

요소 라벨 61개 중 소속이 맞는 라벨 36개 (0.59).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BlindFlange-2 | OperatedValve-2 | n3 | n3 | 병합 |
| BlindFlange-4 | OperatedValve-3 | n5 | n5 | 병합 |
| FlowOutPipeOffPageConnector-1 | PipeReducer-1 | n0 | n14 | X |
| OperatedValve-1 | PipeTee-1 | n2 | j0 | O |
| PipeReducer-1 | ProcessColumn-1 | n14 | n10 | O |
| PipeTee-1 | ProcessColumn-1 | j0 | n10 | O |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j1 | j2 | Nozzle-8 | Nozzle-9 | 오류 |
| j1 | n3 | Nozzle-8 | BlindFlange-2, OperatedValve-2 | 오류 |
| j2 | n10 | Nozzle-9 | Nozzle-1, Nozzle-2, Nozzle-3, Nozzle-4, Nozzle-5, Nozzle-6, Nozzle-7, ProcessColumn-1, SubTaggedColumnSection-1, TaggedColumnSection-1 | 오류 |
| j2 | n5 | Nozzle-9 | BlindFlange-4, OperatedValve-3 | 오류 |
| j3 | j4 | - | - | 오류 |
| j3 | n10 | - | Nozzle-1, Nozzle-2, Nozzle-3, Nozzle-4, Nozzle-5, Nozzle-6, Nozzle-7, ProcessColumn-1, SubTaggedColumnSection-1, TaggedColumnSection-1 | 오류 |
| j4 | n10 | - | Nozzle-1, Nozzle-2, Nozzle-3, Nozzle-4, Nozzle-5, Nozzle-6, Nozzle-7, ProcessColumn-1, SubTaggedColumnSection-1, TaggedColumnSection-1 | 오류 |
| n0 | n1 | FlowOutPipeOffPageConnector-1 | - | 오류 |
| n1 | n19 | - | - | 오류 |
| n14 | n19 | PipeReducer-1 | - | 오류 |
| n3 | n8 | BlindFlange-2, OperatedValve-2 | ProcessInstrumentationFunction-2 | 계측 신호선 |
| n5 | n9 | BlindFlange-4, OperatedValve-3 | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n7 | n8 | ProcessInstrumentationFunction-1 | ProcessInstrumentationFunction-2 | 계측 신호선 |
| n7 | n9 | ProcessInstrumentationFunction-1 | ProcessInstrumentationFunction-3 | 계측 신호선 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 200/150 | PipeReducer | n14 | n14 | O |
| 2765 | FlowOutPipeOffPageConnector | n0 | n0 | O |
| 2750.001 | FlowOutPipeOffPageConnector | n0 | n0 | O |
| W 2765 | FlowOutPipeOffPageConnector | n0 | n0 | O |
| H672B1V | OperatedValve | n2 | n2 | O |
| 80 | OperatedValve | n2 | n2 | O |
| AS9 | OperatedValve | n2 | n2 | O |
| 80/25 | BlindFlange | None | n9 | X |
| H658B1UV | OperatedValve | n3 | n3 | O |
| 2170.8503 | OperatedValve | n3 | n8 | X |
| 25 | OperatedValve | n3 | n3 | O |
| AS9 | OperatedValve | n3 | n9 | X |
| SP | OperatedValve | n3 | n8 | X |
| 2750-5 | OperatedValve | n3 | n8 | X |
| 1) | OperatedValve | n3 | n8 | X |
| 80/25 | BlindFlange | None | n5 | X |
| H658B1UV | OperatedValve | n5 | n5 | O |
| 2170.8503 | OperatedValve | n5 | n9 | X |
| 25 | OperatedValve | n5 | n5 | O |
| AS9 | OperatedValve | n5 | n5 | O |
| SP | OperatedValve | n5 | n9 | X |
| 2750-6 | OperatedValve | n5 | n9 | X |
| 1) | OperatedValve | n5 | n9 | X |
| PIS⁺Z⁺A | ProcessInstrumentationFunction | n7 | n7 | O |
| 275003 | ProcessInstrumentationFunction | n7 | n7 | O |
| PI(Z) | ProcessInstrumentationFunction | n8 | n8 | O |
| 275003A | ProcessInstrumentationFunction | n8 | n8 | O |
| PI(Z) | ProcessInstrumentationFunction | n9 | n9 | O |
| 275003B | ProcessInstrumentationFunction | n9 | n9 | O |
| K 2750 | ProcessColumn | n10 | n10 | O |
| K 2750 | ProcessColumn | n10 | None | X |
| 1 Kolonne | ProcessColumn | n10 | None | X |
| ⌀ 500 x 14000 mm | ProcessColumn | n10 | None | X |
| 1.4571 | ProcessColumn | n10 | None | X |
| pe=6/-1 bar, 150 °C | ProcessColumn | n10 | None | X |
| 1000 | ProcessColumn | n10 | n10 | O |
| Mit Prallblech | ProcessColumn | n10 | n10 | O |
| 16) | ProcessColumn | n10 | n10 | O |
| H1 | Nozzle | n10 | n10 | O |
| 250 | Nozzle | n10 | n10 | O |
| N1 | Nozzle | n10 | n10 | O |
| 200 | Nozzle | n10 | n10 | O |
| N2 | Nozzle | n10 | n10 | O |
| 150 | Nozzle | n10 | n10 | O |
| N3 | Nozzle | n10 | n10 | O |
| 150 | Nozzle | n10 | n10 | O |
| N4 | Nozzle | n10 | n10 | O |
| 200 | Nozzle | n10 | n10 | O |
| N5 | Nozzle | n10 | n10 | O |
| 50 | Nozzle | n10 | n10 | O |
| N7 | Nozzle | n10 | n10 | O |
| 50 | Nozzle | n10 | n10 | O |
| P3 | Nozzle | n10 | None | X |
| 80 | Nozzle | n10 | None | X |
| P4 | Nozzle | n10 | None | X |
| 80 | Nozzle | n10 | None | X |
| KX 2750 | ColumnSection | n10 | None | X |
| KX 2750 | ColumnSection | n10 | None | X |
| 1 Ventilböden | ColumnSection | n10 | None | X |
| ⌀ 600 mm | ColumnSection | n10 | None | X |
| 1.4571 | ColumnSection | n10 | None | X |
