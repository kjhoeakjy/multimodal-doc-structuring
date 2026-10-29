# 정답 대조 결과

정답 인접 쌍 10개 중 1개 복원 (재현율 0.10), 두 요소가 한 노드로 합쳐진 쌍 2개. 그림에 기호가 없는 요소 3개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 0개는 통과 처리. 추출 인접 쌍 59개 중 정답에 없는 쌍 58개. 이 중 25개는 계측 신호선 연결로 배관 정답의 범위 밖이고 33개는 오류임. 배관 쌍 기준 정밀도 0.03.

요소 라벨 26개 중 소속이 맞는 라벨 9개 (0.35).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BlindFlange-1 | OperatedValve-2 | n49 | n49 | 병합 |
| BlindFlange-1 | ProcessColumn-1 | n49 | n7 | X |
| BlindFlange-2 | OperatedValve-2 | n49 | n49 | 병합 |
| BlindFlange-3 | OperatedValve-3 | n71 | None | X |
| BlindFlange-3 | ProcessColumn-1 | n71 | n7 | X |
| BlindFlange-4 | OperatedValve-3 | None | None | X |
| FlowOutPipeOffPageConnector-1 | PipeReducer-1 | n22 | n27 | X |
| OperatedValve-1 | PipeTee-1 | n101 | j4 | O |
| PipeReducer-1 | ProcessColumn-1 | n27 | n7 | X |
| PipeTee-1 | ProcessColumn-1 | j4 | n7 | X |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | j1 | - | - | 오류 |
| j1 | n16 | - | - | 계측 신호선 |
| j1 | n17 | - | - | 오류 |
| j2 | n57 | Nozzle-2 | - | 오류 |
| j2 | n59 | Nozzle-2 | - | 오류 |
| j3 | n93 | Nozzle-4 | - | 오류 |
| j3 | n94 | Nozzle-4 | - | 오류 |
| j4 | n94 | PipeTee-1 | - | 오류 |
| j5 | n10 | - | Nozzle-6 | 오류 |
| j5 | n54 | - | - | 오류 |
| j5 | n71 | - | BlindFlange-3, Nozzle-9 | 오류 |
| n1 | n2 | Nozzle-7 | Nozzle-1, Nozzle-5 | 오류 |
| n1 | n90 | Nozzle-7 | - | 오류 |
| n1 | n93 | Nozzle-7 | - | 오류 |
| n10 | n55 | Nozzle-6 | - | 오류 |
| n10 | n76 | Nozzle-6 | - | 오류 |
| n10 | n8 | Nozzle-6 | - | 오류 |
| n10 | n9 | Nozzle-6 | TaggedColumnSection-1 | 오류 |
| n17 | n21 | - | - | 오류 |
| n2 | n3 | Nozzle-1, Nozzle-5 | - | 오류 |
| n24 | n26 | ProcessInstrumentationFunction-1 | - | 오류 |
| n24 | n28 | ProcessInstrumentationFunction-1 | - | 계측 신호선 |
| n24 | n33 | ProcessInstrumentationFunction-1 | - | 계측 신호선 |
| n26 | n31 | - | - | 계측 신호선 |
| n26 | n32 | - | - | 계측 신호선 |
| n27 | n57 | PipeReducer-1 | - | 오류 |
| n28 | n35 | - | - | 계측 신호선 |
| n29 | n30 | - | - | 계측 신호선 |
| n29 | n33 | - | - | 계측 신호선 |
| n29 | n38 | - | - | 계측 신호선 |
| n3 | n4 | - | SubTaggedColumnSection-1 | 오류 |
| n3 | n5 | - | - | 오류 |
| n30 | n40 | - | - | 계측 신호선 |
| n31 | n41 | - | - | 계측 신호선 |
| n31 | n42 | - | - | 계측 신호선 |
| n32 | n47 | - | - | 계측 신호선 |
| n33 | n36 | - | - | 계측 신호선 |
| n35 | n36 | - | - | 계측 신호선 |
| n38 | n39 | - | - | 계측 신호선 |
| n38 | n50 | - | - | 계측 신호선 |
| n39 | n40 | - | - | 계측 신호선 |
| n4 | n6 | SubTaggedColumnSection-1 | - | 오류 |
| n40 | n49 | - | BlindFlange-1, BlindFlange-2, Nozzle-8, OperatedValve-2, ProcessInstrumentationFunction-2 | 계측 신호선 |
| n42 | n43 | - | - | 계측 신호선 |
| n43 | n44 | - | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n44 | n45 | ProcessInstrumentationFunction-3 | - | 계측 신호선 |
| n45 | n46 | - | - | 계측 신호선 |
| n46 | n47 | - | - | 계측 신호선 |
| n49 | n50 | BlindFlange-1, BlindFlange-2, Nozzle-8, OperatedValve-2, ProcessInstrumentationFunction-2 | - | 계측 신호선 |
| n49 | n71 | BlindFlange-1, BlindFlange-2, Nozzle-8, OperatedValve-2, ProcessInstrumentationFunction-2 | BlindFlange-3, Nozzle-9 | 오류 |
| n5 | n6 | - | - | 오류 |
| n54 | n57 | - | - | 오류 |
| n55 | n59 | - | - | 오류 |
| n6 | n7 | - | Nozzle-3, ProcessColumn-1 | 오류 |
| n7 | n8 | Nozzle-3, ProcessColumn-1 | - | 오류 |
| n7 | n9 | Nozzle-3, ProcessColumn-1 | TaggedColumnSection-1 | 오류 |
| n91 | n95 | - | - | 오류 |
| n94 | n95 | - | - | 오류 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 2750.001 | FlowOutPipeOffPageConnector | n22 | n22 | O |
| H672B1V | OperatedValve | n101 | n101 | O |
| 80 | OperatedValve | n101 | n101 | O |
| AS9 | OperatedValve | n101 | n101 | O |
| 80/25 | BlindFlange | n49 | n49 | O |
| 80/25 | BlindFlange | n71 | n71 | O |
| PI(Z) | ProcessInstrumentationFunction | n49 | n39 | X |
| 1.4571 | ProcessColumn | n7 | n96 | X |
| Mit Prallblech | ProcessColumn | n7 | n2 | X |
| 16) | ProcessColumn | n7 | n93 | X |
| 250 | Nozzle | n7 | n2 | X |
| 200 | Nozzle | n7 | n57 | X |
| N2 | Nozzle | n7 | n7 | O |
| 150 | Nozzle | n7 | n7 | O |
| 150 | Nozzle | n7 | n95 | X |
| N4 | Nozzle | n7 | n2 | X |
| 200 | Nozzle | n7 | n2 | X |
| 50 | Nozzle | n7 | n10 | X |
| 50 | Nozzle | n7 | n86 | X |
| P3 | Nozzle | n7 | n49 | X |
| 80 | Nozzle | n7 | n49 | X |
| P4 | Nozzle | n7 | n71 | X |
| 80 | Nozzle | n7 | n71 | X |
| KX 2750 | ColumnSection | n9 | n9 | O |
| KX 2750 | ColumnSection | n9 | n97 | X |
| 1.4571 | ColumnSection | n9 | n97 | X |
