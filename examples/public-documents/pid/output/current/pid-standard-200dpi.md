# 정답 대조 결과

정답 인접 쌍 26개 중 19개 복원 (재현율 0.73), 두 요소가 한 노드로 합쳐진 쌍 6개. 그림에 기호가 없는 요소 11개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 1개는 통과 처리. 추출 인접 쌍 59개 중 정답에 없는 쌍 40개. 이 중 5개는 계측 신호선 연결로 배관 정답의 범위 밖이고 35개는 오류임. 배관 쌍 기준 정밀도 0.35.

요소 라벨 40개 중 소속이 맞는 라벨 32개 (0.80).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n42 | n44 | O |
| BallValve-1 | ReciprocatingPump-1 | n42 | n3 | O |
| BallValve-2 | PipeTee-2 | n46 | n46 | 병합 |
| BallValve-3 | BlindFlange-1 | n36 | n36 | 병합 |
| BallValve-3 | PipeTee-3 | n36 | n36 | 병합 |
| BallValve-5 | BlindFlange-2 | n37 | n37 | 병합 |
| BallValve-5 | PipeTee-5 | n37 | n37 | 병합 |
| ButterflyValve-1 | SwingCheckValve-1 | n35 | n41 | O |
| ButterflyValve-1 | Tank-1 | n35 | n5 | O |
| CentrifugalPump-1 | FlowInPipeOffPageConnector-1 | n1 | n45 | O |
| CentrifugalPump-1 | PlateHeatExchanger-1 | n1 | n2 | O |
| FlowOutPipeOffPageConnector-1 | PipeTee-5 | n39 | n37 | X |
| GlobeValve-1 | Tank-1 | n15 | n5 | O |
| GlobeValve-1 | TubularHeatExchanger-1 | n15 | n4 | O |
| GlobeValve-2 | PlateHeatExchanger-1 | n21 | n2 | O |
| GlobeValve-2 | Tank-1 | n21 | n5 | O |
| GlobeValve-3 | TubularHeatExchanger-1 | n17 | n4 | O |
| PipeReducer-1 | SwingCheckValve-1 | n44 | n41 | O |
| PipeTee-1 | PipeTee-2 | j3 | n46 | O |
| PipeTee-1 | PipeTee-3 | j3 | n36 | O |
| PipeTee-1 | SpringLoadedGlobeSafetyValve-1 | j3 | n13 | O |
| PipeTee-2 | ReciprocatingPump-1 | n46 | n3 | O |
| PipeTee-3 | PipeTee-4 | n36 | n4 | O |
| PipeTee-4 | PipeTee-5 | n4 | n37 | O |
| PipeTee-4 | TubularHeatExchanger-1 | n4 | n4 | 병합 |
| SpringLoadedGlobeSafetyValve-1 | Tank-1 | n13 | n5 | O |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | n48 | ProcessInstrumentationFunction-4 | - | 오류 |
| j0 | n5 | ProcessInstrumentationFunction-4 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j1 | n32 | ProcessInstrumentationFunction-2 | - | 오류 |
| j10 | j11 | - | - | 오류 |
| j10 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j11 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j12 | j13 | - | - | 오류 |
| j12 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j13 | j14 | - | - | 오류 |
| j13 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j14 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j15 | j16 | - | - | 오류 |
| j15 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j16 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j17 | j18 | - | - | 오류 |
| j17 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j18 | j19 | - | - | 오류 |
| j18 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j19 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j2 | n37 | - | BallValve-5, BlindFlange-2, PipeTee-5 | 오류 |
| j4 | j5 | - | - | 오류 |
| j4 | n5 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j5 | n5 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j6 | j7 | - | - | 오류 |
| j6 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, PipeTee-4, TubularHeatExchanger-1 | 오류 |
| j7 | j8 | - | - | 오류 |
| j8 | j9 | - | - | 오류 |
| j8 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, PipeTee-4, TubularHeatExchanger-1 | 오류 |
| j9 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, PipeTee-4, TubularHeatExchanger-1 | 오류 |
| n10 | n8 | - | - | 계측 신호선 |
| n11 | n17 | - | GlobeValve-3 | 오류 |
| n11 | n9 | - | - | 오류 |
| n19 | n20 | - | - | 계측 신호선 |
| n19 | n22 | - | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n20 | n23 | - | - | 오류 |
| n21 | n23 | GlobeValve-2 | - | 오류 |
| n30 | n31 | ProcessInstrumentationFunction-1 | - | 계측 신호선 |
| n32 | n34 | - | - | 오류 |
| n32 | n79 | - | - | 오류 |
| n8 | n9 | - | - | 계측 신호선 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 75SA21-80 | SwingCheckValve | n41 | n41 | O |
| 80/50 | PipeReducer | n44 | n43 | X |
| SV 104.01 | SpringLoadedGlobeSafetyValve | n13 | n13 | O |
| PI | ProcessInstrumentationFunction | n30 | n30 | O |
| 4712.01 | ProcessInstrumentationFunction | n30 | n30 | O |
| PICSA | ProcessInstrumentationFunction | j1 | n33 | X |
| 4712.02 | ProcessInstrumentationFunction | j1 | n32 | X |
| HS | ProcessInstrumentationFunction | n22 | n19 | X |
| 4750.01 | ProcessInstrumentationFunction | n22 | n19 | X |
| TICSA | ProcessInstrumentationFunction | j0 | n8 | X |
| 4750.03 | ProcessInstrumentationFunction | j0 | n8 | X |
| 80 | Nozzle | n2 | n2 | O |
| N2 | Nozzle | n2 | n2 | O |
| 80 | Nozzle | n2 | n2 | O |
| N3 | Nozzle | n2 | n2 | O |
| 50 | Nozzle | n2 | n2 | O |
| N4 | Nozzle | n2 | n2 | O |
| 50 | Nozzle | n2 | n2 | O |
| 50 | Nozzle | n4 | n4 | O |
| N4 | Nozzle | n4 | n4 | O |
| 50 | Nozzle | n4 | n4 | O |
| P4711 | CentrifugalPump | n1 | n1 | O |
| 80 | Nozzle | n1 | n1 | O |
| N2 | Nozzle | n1 | n1 | O |
| 80 | Nozzle | n1 | n1 | O |
| P4712 | ReciprocatingPump | n3 | n3 | O |
| 50 | Nozzle | n3 | n3 | O |
| N2 | Nozzle | n3 | n3 | O |
| 50 | Nozzle | n3 | n3 | O |
| T4750 | Tank | n5 | n5 | O |
| 80 | Nozzle | n5 | n5 | O |
| N2 | Nozzle | n5 | n5 | O |
| 80 | Nozzle | n5 | n35 | X |
| 50 | Nozzle | n5 | n5 | O |
| N6 | Nozzle | n5 | n5 | O |
| 50 | Nozzle | n5 | n5 | O |
| N7 | Nozzle | n5 | n5 | O |
| 25 | Nozzle | n5 | n5 | O |
| N8 | Nozzle | n5 | n5 | O |
| 800 | Nozzle | n5 | n5 | O |
