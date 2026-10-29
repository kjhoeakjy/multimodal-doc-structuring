# 정답 대조 결과

정답 인접 쌍 26개 중 14개 복원 (재현율 0.54), 두 요소가 한 노드로 합쳐진 쌍 5개. 그림에 기호가 없는 요소 11개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 1개는 통과 처리. 추출 인접 쌍 70개 중 정답에 없는 쌍 57개. 이 중 5개는 계측 신호선 연결로 배관 정답의 범위 밖이고 52개는 오류임. 배관 쌍 기준 정밀도 0.20.

요소 라벨 40개 중 소속이 맞는 라벨 15개 (0.38).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n112 | n121 | O |
| BallValve-1 | ReciprocatingPump-1 | n112 | n3 | O |
| BallValve-2 | PipeTee-2 | n123 | n123 | 병합 |
| BallValve-3 | BlindFlange-1 | n103 | n103 | 병합 |
| BallValve-3 | PipeTee-3 | n103 | n103 | 병합 |
| BallValve-5 | BlindFlange-2 | n104 | n104 | 병합 |
| BallValve-5 | PipeTee-5 | n104 | n104 | 병합 |
| ButterflyValve-1 | SwingCheckValve-1 | n94 | n111 | X |
| ButterflyValve-1 | Tank-1 | n94 | n10 | O |
| CentrifugalPump-1 | FlowInPipeOffPageConnector-1 | n1 | n107 | O |
| CentrifugalPump-1 | PlateHeatExchanger-1 | n1 | n98 | X |
| FlowOutPipeOffPageConnector-1 | PipeTee-5 | n108 | n104 | X |
| GlobeValve-1 | Tank-1 | n9 | n10 | X |
| GlobeValve-1 | TubularHeatExchanger-1 | n9 | n7 | O |
| GlobeValve-2 | PlateHeatExchanger-1 | n64 | n98 | X |
| GlobeValve-2 | Tank-1 | n64 | n10 | X |
| GlobeValve-3 | TubularHeatExchanger-1 | n9 | n7 | O |
| PipeReducer-1 | SwingCheckValve-1 | n121 | n111 | O |
| PipeTee-1 | PipeTee-2 | j2 | n123 | O |
| PipeTee-1 | PipeTee-3 | j2 | n103 | O |
| PipeTee-1 | SpringLoadedGlobeSafetyValve-1 | j2 | n33 | O |
| PipeTee-2 | ReciprocatingPump-1 | n123 | n3 | O |
| PipeTee-3 | PipeTee-4 | n103 | n5 | O |
| PipeTee-4 | PipeTee-5 | n5 | n104 | O |
| PipeTee-4 | TubularHeatExchanger-1 | n5 | n7 | O |
| SpringLoadedGlobeSafetyValve-1 | Tank-1 | n33 | n10 | X |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | n10 | ProcessInstrumentationFunction-4 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j1 | n85 | ProcessInstrumentationFunction-2 | - | 오류 |
| j10 | j11 | - | - | 오류 |
| j10 | n6 | - | Nozzle-13, Nozzle-4 | 오류 |
| j10 | n97 | - | - | 오류 |
| j11 | j12 | - | - | 오류 |
| j11 | n97 | - | - | 오류 |
| j12 | n2 | - | Nozzle-14, Nozzle-3 | 오류 |
| j13 | n2 | - | Nozzle-14, Nozzle-3 | 오류 |
| j14 | n6 | - | Nozzle-13, Nozzle-4 | 오류 |
| j15 | j16 | - | - | 오류 |
| j15 | n6 | - | Nozzle-13, Nozzle-4 | 오류 |
| j16 | j17 | - | - | 오류 |
| j16 | n98 | - | PlateHeatExchanger-1 | 오류 |
| j17 | n2 | - | Nozzle-14, Nozzle-3 | 오류 |
| j17 | n98 | - | PlateHeatExchanger-1 | 오류 |
| j18 | n2 | - | Nozzle-14, Nozzle-3 | 오류 |
| j3 | j4 | - | - | 오류 |
| j3 | n10 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j4 | n10 | - | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | 오류 |
| j5 | j6 | - | - | 오류 |
| j5 | n9 | - | GlobeValve-1, GlobeValve-3, Nozzle-11, Nozzle-16 | 오류 |
| j6 | n88 | - | - | 오류 |
| j7 | j8 | - | - | 오류 |
| j7 | n7 | - | TubularHeatExchanger-1 | 오류 |
| j8 | n5 | - | Nozzle-10, Nozzle-15, PipeTee-4 | 오류 |
| j9 | n6 | - | Nozzle-13, Nozzle-4 | 오류 |
| n1 | n4 | CentrifugalPump-1, Nozzle-1 | - | 오류 |
| n10 | n20 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | - | 오류 |
| n10 | n28 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | - | 오류 |
| n10 | n40 | Nozzle-12, Nozzle-17, Nozzle-18, Nozzle-19, Nozzle-5, Nozzle-6, Nozzle-8, Tank-1 | - | 오류 |
| n103 | n148 | BallValve-3, BlindFlange-1, PipeTee-3 | ProcessInstrumentationFunction-1 | 계측 신호선 |
| n104 | n124 | BallValve-5, BlindFlange-2, PipeTee-5 | - | 오류 |
| n104 | n149 | BallValve-5, BlindFlange-2, PipeTee-5 | - | 오류 |
| n105 | n120 | - | Nozzle-2 | 오류 |
| n105 | n2 | - | Nozzle-14, Nozzle-3 | 오류 |
| n108 | n110 | FlowOutPipeOffPageConnector-1 | - | 오류 |
| n110 | n124 | - | - | 오류 |
| n120 | n4 | Nozzle-2 | - | 오류 |
| n125 | n126 | - | - | 오류 |
| n131 | n132 | - | - | 오류 |
| n131 | n5 | - | Nozzle-10, Nozzle-15, PipeTee-4 | 오류 |
| n148 | n83 | ProcessInstrumentationFunction-1 | - | 오류 |
| n15 | n16 | - | - | 계측 신호선 |
| n15 | n17 | - | - | 계측 신호선 |
| n16 | n18 | - | - | 오류 |
| n19 | n20 | - | - | 오류 |
| n2 | n98 | Nozzle-14, Nozzle-3 | PlateHeatExchanger-1 | 오류 |
| n33 | n36 | SpringLoadedGlobeSafetyValve-1 | - | 오류 |
| n36 | n40 | - | - | 오류 |
| n6 | n97 | Nozzle-13, Nozzle-4 | - | 오류 |
| n64 | n8 | GlobeValve-2 | ProcessInstrumentationFunction-3 | 계측 신호선 |
| n7 | n88 | TubularHeatExchanger-1 | - | 오류 |
| n82 | n83 | - | - | 계측 신호선 |
| n85 | n92 | - | - | 오류 |
| n85 | n93 | - | - | 오류 |
| n97 | n98 | - | PlateHeatExchanger-1 | 오류 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 75SA21-80 | SwingCheckValve | n111 | n111 | O |
| 80/50 | PipeReducer | n121 | n117 | X |
| SV 104.01 | SpringLoadedGlobeSafetyValve | n33 | n41 | X |
| PI | ProcessInstrumentationFunction | n148 | n82 | X |
| 4712.01 | ProcessInstrumentationFunction | n148 | n82 | X |
| PICSA | ProcessInstrumentationFunction | j1 | n86 | X |
| 4712.02 | ProcessInstrumentationFunction | j1 | n85 | X |
| HS | ProcessInstrumentationFunction | n8 | n8 | O |
| 4750.01 | ProcessInstrumentationFunction | n8 | n8 | O |
| TICSA | ProcessInstrumentationFunction | j0 | n15 | X |
| 4750.03 | ProcessInstrumentationFunction | j0 | n15 | X |
| 80 | Nozzle | n98 | n2 | X |
| N2 | Nozzle | n98 | n6 | X |
| 80 | Nozzle | n98 | n6 | X |
| N3 | Nozzle | n98 | n6 | X |
| 50 | Nozzle | n98 | n6 | X |
| N4 | Nozzle | n98 | n2 | X |
| 50 | Nozzle | n98 | n2 | X |
| 50 | Nozzle | n7 | n5 | X |
| N4 | Nozzle | n7 | n5 | X |
| 50 | Nozzle | n7 | n5 | X |
| P4711 | CentrifugalPump | n1 | n105 | X |
| 80 | Nozzle | n1 | n1 | O |
| N2 | Nozzle | n1 | n105 | X |
| 80 | Nozzle | n1 | n120 | X |
| P4712 | ReciprocatingPump | n3 | n106 | X |
| 50 | Nozzle | n3 | n3 | O |
| N2 | Nozzle | n3 | n106 | X |
| 50 | Nozzle | n3 | n122 | X |
| T4750 | Tank | n10 | n10 | O |
| 80 | Nozzle | n10 | n10 | O |
| N2 | Nozzle | n10 | n10 | O |
| 80 | Nozzle | n10 | n94 | X |
| 50 | Nozzle | n10 | n10 | O |
| N6 | Nozzle | n10 | n10 | O |
| 50 | Nozzle | n10 | n10 | O |
| N7 | Nozzle | n10 | n10 | O |
| 25 | Nozzle | n10 | n10 | O |
| N8 | Nozzle | n10 | n10 | O |
| 800 | Nozzle | n10 | n10 | O |
