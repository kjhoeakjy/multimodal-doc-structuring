# 정답 대조 결과

정답 인접 쌍 9개 중 4개 복원 (재현율 0.44), 두 요소가 한 노드로 합쳐진 쌍 1개. 그림에 기호가 없는 요소 0개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 0개는 통과 처리. 추출 인접 쌍 14개 중 정답에 없는 쌍 10개. 이 중 5개는 계측 신호선 연결로 배관 정답의 범위 밖이고 5개는 오류임. 배관 쌍 기준 정밀도 0.44.

요소 라벨 4개 중 소속이 맞는 라벨 4개 (1.00).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n8 | n2 | X |
| BallValve-1 | RestrictionOrifice-1 | n8 | n20 | X |
| BlindFlange-1 | Flange-1 | n1 | n17 | O |
| BlindFlange-1 | PipeFitting-1 | n1 | n1 | 병합 |
| Flange-1 | Flange-2 | n17 | n18 | O |
| Flange-2 | OperatedValve-1 | n18 | n7 | O |
| Flange-3 | OperatedValve-1 | n19 | n7 | O |
| Flange-3 | RestrictionOrifice-1 | n19 | n20 | X |
| FlowOutPipeOffPageConnector-1 | PipeReducer-1 | n3 | n2 | X |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | n0 | - | - | 계측 신호선 |
| j0 | n16 | - | - | 계측 신호선 |
| j1 | n19 | - | Flange-3 | 오류 |
| j2 | n14 | - | - | 오류 |
| n0 | n7 | - | OperatedValve-1 | 계측 신호선 |
| n12 | n20 | - | RestrictionOrifice-1 | 오류 |
| n13 | n2 | - | PipeReducer-1 | 오류 |
| n14 | n3 | - | FlowOutPipeOffPageConnector-1 | 오류 |
| n15 | n16 | - | - | 계측 신호선 |
| n16 | n5 | - | ProcessInstrumentationFunction-1 | 계측 신호선 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| 0200x0800 | PipeReducer | n2 | n2 | O |
| ESV | ProcessInstrumentationFunction | n5 | n5 | O |
| 3712 | ProcessInstrumentationFunction | n5 | n5 | O |
| D-13 | ProcessInstrumentationFunction | n5 | n5 | O |
