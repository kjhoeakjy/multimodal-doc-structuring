# 정답 대조 결과

정답 인접 쌍 27개 중 27개 복원 (재현율 1.00). 추출 인접 쌍 34개 중 정답에 없는 쌍 7개. 이 중 6개는 계측 신호선 연결로 배관 정답의 범위 밖이고 1개는 오류임. 배관 쌍 기준 정밀도 0.96.

요소 라벨 62개 중 소속이 맞는 라벨 60개 (0.97).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n3 | n29 | O |
| BallValve-1 | ReciprocatingPump-1 | n3 | n25 | O |
| BallValve-2 | PipeTee-2 | n7 | j2 | O |
| BallValve-3 | BlindFlange-1 | n8 | n44 | O |
| BallValve-3 | PipeTee-3 | n8 | j1 | O |
| BallValve-4 | PipeTee-3 | n9 | j1 | O |
| BallValve-4 | PipeTee-4 | n9 | j3 | O |
| BallValve-5 | BlindFlange-2 | n10 | n45 | O |
| BallValve-5 | PipeTee-5 | n10 | j4 | O |
| ButterflyValve-1 | SwingCheckValve-1 | n1 | n2 | O |
| ButterflyValve-1 | Tank-1 | n1 | n21 | O |
| CentrifugalPump-1 | FlowInPipeOffPageConnector-1 | n24 | n26 | O |
| CentrifugalPump-1 | PlateHeatExchanger-1 | n24 | n18 | O |
| FlowOutPipeOffPageConnector-1 | PipeTee-5 | n11 | j4 | O |
| GlobeValve-1 | Tank-1 | n12 | n21 | O |
| GlobeValve-1 | TubularHeatExchanger-1 | n12 | n19 | O |
| GlobeValve-2 | PlateHeatExchanger-1 | n0 | n18 | O |
| GlobeValve-2 | Tank-1 | n0 | n21 | O |
| GlobeValve-3 | TubularHeatExchanger-1 | n13 | n19 | O |
| PipeReducer-1 | SwingCheckValve-1 | n29 | n2 | O |
| PipeTee-1 | PipeTee-2 | j0 | j2 | O |
| PipeTee-1 | PipeTee-3 | j0 | j1 | O |
| PipeTee-1 | SpringLoadedGlobeSafetyValve-1 | j0 | n4 | O |
| PipeTee-2 | ReciprocatingPump-1 | j2 | n25 | O |
| PipeTee-4 | PipeTee-5 | j3 | j4 | O |
| PipeTee-4 | TubularHeatExchanger-1 | j3 | n19 | O |
| SpringLoadedGlobeSafetyValve-1 | Tank-1 | n4 | n21 | O |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| n0 | n16 | GlobeValve-2 | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n12 | n23 | GlobeValve-1 | - | 오류 |
| n13 | n17 | GlobeValve-3 | ProcessInstrumentationFunction-4 | 계측 신호선 |
| n14 | n44 | ProcessInstrumentationFunction-1 | BlindFlange-1 | 계측 신호선 |
| n15 | n23 | ProcessInstrumentationFunction-2 | - | 계측 신호선 |
| n15 | n45 | ProcessInstrumentationFunction-2 | BlindFlange-2 | 계측 신호선 |
| n17 | n21 | ProcessInstrumentationFunction-4 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 계측 신호선 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 66KL21-80 | ButterflyValve | n1 | n1 | O |
| 75SA21-80 | SwingCheckValve | n2 | n2 | O |
| 80/50 | PipeReducer | n29 | n29 | O |
| 73KH12-50 | BallValve | n3 | n3 | O |
| SV 104.01 | SpringLoadedGlobeSafetyValve | n4 | n4 | O |
| P = 6 barg | SpringLoadedGlobeSafetyValve | n4 | n4 | O |
| DN = 25/50 | SpringLoadedGlobeSafetyValve | n4 | n4 | O |
| 73KH12-25 | BallValve | n7 | n7 | O |
| 73KH12-25 | BallValve | n8 | n8 | O |
| 73KH12-50 | BallValve | n9 | n9 | O |
| 73KH12-25 | BallValve | n10 | n10 | O |
| PI | ProcessInstrumentationFunction | n14 | n14 | O |
| 4712.01 | ProcessInstrumentationFunction | n14 | n14 | O |
| PICSA | ProcessInstrumentationFunction | n15 | n15 | O |
| 4712.02 | ProcessInstrumentationFunction | n15 | n15 | O |
| HS | ProcessInstrumentationFunction | n16 | n16 | O |
| 4750.01 | ProcessInstrumentationFunction | n16 | n16 | O |
| TICSA | ProcessInstrumentationFunction | n17 | n17 | O |
| 4750.03 | ProcessInstrumentationFunction | n17 | n17 | O |
| H1007 | PlateHeatExchanger | n18 | n18 | O |
| N1 | Nozzle | n18 | n18 | O |
| 80 | Nozzle | n18 | n18 | O |
| N2 | Nozzle | n18 | n18 | O |
| 80 | Nozzle | n18 | n18 | O |
| N3 | Nozzle | n18 | n18 | O |
| 50 | Nozzle | n18 | n18 | O |
| N4 | Nozzle | n18 | n18 | O |
| 50 | Nozzle | n18 | n18 | O |
| H1008 | TubularHeatExchanger | n19 | n19 | O |
| N1 | Nozzle | n19 | n19 | O |
| 50 | Nozzle | n19 | n19 | O |
| N2 | Nozzle | n19 | n19 | O |
| 50 | Nozzle | n19 | n19 | O |
| N3 | Nozzle | n19 | n19 | O |
| 50 | Nozzle | n19 | n19 | O |
| N4 | Nozzle | n19 | n19 | O |
| 50 | Nozzle | n19 | n19 | O |
| P4711 | CentrifugalPump | n24 | n24 | O |
| N1 | Nozzle | n24 | n24 | O |
| 80 | Nozzle | n24 | n24 | O |
| N2 | Nozzle | n24 | n24 | O |
| 80 | Nozzle | n24 | n24 | O |
| P4712 | ReciprocatingPump | n25 | n25 | O |
| N1 | Nozzle | n25 | n25 | O |
| 50 | Nozzle | n25 | n25 | O |
| N2 | Nozzle | n25 | n25 | O |
| 50 | Nozzle | n25 | n25 | O |
| T4750 | Tank | n21 | n21 | O |
| N1 | Nozzle | n21 | n21 | O |
| 80 | Nozzle | n21 | n21 | O |
| N2 | Nozzle | n21 | n21 | O |
| 80 | Nozzle | n21 | n21 | O |
| N3 | Nozzle | n21 | n21 | O |
| 80 | Nozzle | n21 | n21 | O |
| N5 | Nozzle | n21 | n21 | O |
| 50 | Nozzle | n21 | n21 | O |
| N6 | Nozzle | n21 | n21 | O |
| 50 | Nozzle | n21 | n21 | O |
| N7 | Nozzle | n21 | n21 | O |
| 25 | Nozzle | n21 | n21 | O |
| N8 | Nozzle | n21 | None | X |
| 800 | Nozzle | n21 | None | X |
