# 정답 대조 결과

정답 인접 쌍 24개 중 17개 복원 (재현율 0.71), 두 요소가 한 노드로 합쳐진 쌍 3개. 그림에 기호가 없는 요소 11개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 3개는 통과 처리. 추출 인접 쌍 67개 중 정답에 없는 쌍 50개. 이 중 3개는 계측 신호선 연결로 배관 정답의 범위 밖이고 47개는 오류임. 배관 쌍 기준 정밀도 0.27.

요소 라벨 31개 중 소속이 맞는 라벨 28개 (0.90).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n35 | n38 | X |
| BallValve-1 | ReciprocatingPump-1 | n35 | n3 | O |
| BallValve-2 | PipeTee-2 | n39 | n39 | 병합 |
| BallValve-3 | PipeTee-3 | n72 | n72 | 병합 |
| BallValve-4 | PipeTee-3 | n36 | n72 | O |
| BallValve-4 | PipeTee-4 | n36 | j7 | O |
| BallValve-5 | PipeTee-5 | n73 | n73 | 병합 |
| CentrifugalPump-1 | FlowInPipeOffPageConnector-1 | n1 | n32 | O |
| CentrifugalPump-1 | PlateHeatExchanger-1 | n1 | n2 | O |
| FlowOutPipeOffPageConnector-1 | PipeTee-5 | n33 | n73 | O |
| GlobeValve-1 | Tank-1 | n19 | n6 | O |
| GlobeValve-1 | TubularHeatExchanger-1 | n19 | n4 | X |
| GlobeValve-2 | PlateHeatExchanger-1 | n24 | n2 | O |
| GlobeValve-2 | Tank-1 | n24 | n6 | O |
| GlobeValve-3 | TubularHeatExchanger-1 | n23 | n4 | O |
| PipeReducer-1 | SwingCheckValve-1 | n38 | n34 | O |
| PipeTee-1 | PipeTee-2 | j6 | n39 | O |
| PipeTee-1 | PipeTee-3 | j6 | n72 | O |
| PipeTee-1 | SpringLoadedGlobeSafetyValve-1 | j6 | n17 | O |
| PipeTee-2 | ReciprocatingPump-1 | n39 | n3 | O |
| PipeTee-4 | PipeTee-5 | j7 | n73 | X |
| PipeTee-4 | TubularHeatExchanger-1 | j7 | n4 | O |
| SpringLoadedGlobeSafetyValve-1 | Tank-1 | n17 | n6 | X |
| SwingCheckValve-1 | Tank-1 | n34 | n6 | O |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | n44 | ProcessInstrumentationFunction-4 | - | 오류 |
| j0 | n45 | ProcessInstrumentationFunction-4 | - | 오류 |
| j0 | n6 | ProcessInstrumentationFunction-4 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Tank-1 | 오류 |
| j1 | n6 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Tank-1 | 계측 신호선 |
| j10 | j11 | - | - | 오류 |
| j10 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, TubularHeatExchanger-1 | 오류 |
| j11 | j12 | - | - | 오류 |
| j12 | j13 | - | - | 오류 |
| j12 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, TubularHeatExchanger-1 | 오류 |
| j13 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, TubularHeatExchanger-1 | 오류 |
| j14 | j15 | - | - | 오류 |
| j14 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j15 | j16 | - | - | 오류 |
| j16 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j17 | j18 | - | - | 오류 |
| j17 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j18 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j19 | j20 | - | - | 오류 |
| j19 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j2 | j4 | - | - | 오류 |
| j2 | n19 | - | GlobeValve-1 | 오류 |
| j20 | j21 | - | - | 오류 |
| j20 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j21 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j22 | j23 | - | - | 오류 |
| j22 | n2 | - | Nozzle-13, Nozzle-14, Nozzle-3, Nozzle-4, PlateHeatExchanger-1 | 오류 |
| j3 | j4 | - | - | 오류 |
| j3 | n4 | - | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, TubularHeatExchanger-1 | 오류 |
| j5 | n19 | ProcessInstrumentationFunction-2 | GlobeValve-1 | 오류 |
| j5 | n28 | ProcessInstrumentationFunction-2 | - | 오류 |
| j8 | j9 | - | - | 오류 |
| j8 | n6 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Tank-1 | 오류 |
| j9 | n6 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Tank-1 | 오류 |
| n10 | n11 | - | - | 오류 |
| n10 | n9 | - | - | 오류 |
| n13 | n14 | - | - | 오류 |
| n13 | n15 | - | - | 오류 |
| n14 | n42 | - | - | 오류 |
| n15 | n22 | - | - | 오류 |
| n17 | n54 | SpringLoadedGlobeSafetyValve-1 | Nozzle-8 | 오류 |
| n24 | n5 | GlobeValve-2 | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n26 | n27 | - | - | 계측 신호선 |
| n27 | n85 | - | ProcessInstrumentationFunction-1 | 오류 |
| n28 | n30 | - | - | 오류 |
| n28 | n31 | - | - | 오류 |
| n35 | n37 | BallValve-1 | - | 오류 |
| n4 | n73 | Nozzle-10, Nozzle-11, Nozzle-15, Nozzle-16, TubularHeatExchanger-1 | BallValve-5, PipeTee-5 | 오류 |
| n54 | n6 | Nozzle-8 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Tank-1 | 오류 |
| n72 | n85 | BallValve-3, PipeTee-3 | ProcessInstrumentationFunction-1 | 오류 |
| n73 | n86 | BallValve-5, PipeTee-5 | - | 오류 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| PI | ProcessInstrumentationFunction | n85 | n26 | X |
| 4712.01 | ProcessInstrumentationFunction | n85 | n26 | X |
| PICSA | ProcessInstrumentationFunction | j5 | n29 | X |
| HS | ProcessInstrumentationFunction | n5 | n5 | O |
| 80 | Nozzle | n2 | n2 | O |
| N2 | Nozzle | n2 | n2 | O |
| 80 | Nozzle | n2 | n2 | O |
| N3 | Nozzle | n2 | n2 | O |
| 50 | Nozzle | n2 | n2 | O |
| N4 | Nozzle | n2 | n2 | O |
| 50 | Nozzle | n4 | n4 | O |
| N2 | Nozzle | n4 | n4 | O |
| 50 | Nozzle | n4 | n4 | O |
| N3 | Nozzle | n4 | n4 | O |
| 50 | Nozzle | n4 | n4 | O |
| N4 | Nozzle | n4 | n4 | O |
| 50 | Nozzle | n4 | n4 | O |
| 80 | Nozzle | n1 | n1 | O |
| N2 | Nozzle | n1 | n1 | O |
| 80 | Nozzle | n1 | n1 | O |
| P4712 | ReciprocatingPump | n3 | n3 | O |
| N2 | Nozzle | n3 | n3 | O |
| 50 | Nozzle | n3 | n3 | O |
| T4750 | Tank | n6 | n6 | O |
| 80 | Nozzle | n6 | n6 | O |
| N2 | Nozzle | n6 | n6 | O |
| 80 | Nozzle | n6 | n6 | O |
| N6 | Nozzle | n6 | n6 | O |
| 50 | Nozzle | n6 | n6 | O |
| N7 | Nozzle | n6 | n6 | O |
| 800 | Nozzle | n6 | n6 | O |
