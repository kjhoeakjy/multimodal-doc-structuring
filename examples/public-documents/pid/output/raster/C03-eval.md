# 정답 대조 결과

정답 인접 쌍 9개 중 2개 복원 (재현율 0.22), 두 요소가 한 노드로 합쳐진 쌍 1개. 그림에 기호가 없는 요소 0개와 관련된 쌍 0개는 제외, 선 위 표식으로만 그려진 부품 0개는 통과 처리. 추출 인접 쌍 28개 중 정답에 없는 쌍 26개. 이 중 14개는 계측 신호선 연결로 배관 정답의 범위 밖이고 12개는 오류임. 배관 쌍 기준 정밀도 0.14.

요소 라벨 2개 중 소속이 맞는 라벨 2개 (1.00).

## 정답 인접 쌍

| 정답 A | 정답 B | 추출 A | 추출 B | 복원 |
|---|---|---|---|---|
| BallValve-1 | PipeReducer-1 | n0 | n25 | X |
| BallValve-1 | RestrictionOrifice-1 | n0 | n29 | X |
| BlindFlange-1 | Flange-1 | n23 | n37 | X |
| BlindFlange-1 | PipeFitting-1 | n23 | n23 | 병합 |
| Flange-1 | Flange-2 | n37 | n39 | X |
| Flange-2 | OperatedValve-1 | n39 | n1 | O |
| Flange-3 | OperatedValve-1 | n40 | n1 | O |
| Flange-3 | RestrictionOrifice-1 | n40 | n29 | X |
| FlowOutPipeOffPageConnector-1 | PipeReducer-1 | n5 | n25 | X |

## 정답에 없는 추출 쌍

| 추출 A | 추출 B | 대응 정답 A | 대응 정답 B | 종류 |
|---|---|---|---|---|
| j0 | n2 | - | - | 오류 |
| j1 | j6 | - | - | 오류 |
| j1 | n2 | - | - | 오류 |
| j2 | n28 | - | - | 계측 신호선 |
| j2 | n38 | - | - | 오류 |
| j2 | n40 | - | Flange-3 | 오류 |
| j3 | n16 | - | - | 계측 신호선 |
| j3 | n5 | - | FlowOutPipeOffPageConnector-1 | 오류 |
| j4 | n13 | - | - | 계측 신호선 |
| j4 | n2 | - | - | 계측 신호선 |
| j4 | n3 | - | ProcessInstrumentationFunction-1 | 계측 신호선 |
| j5 | n2 | - | - | 오류 |
| j6 | n2 | - | - | 오류 |
| j7 | n25 | - | PipeReducer-1 | 오류 |
| n1 | n2 | OperatedValve-1 | - | 오류 |
| n1 | n22 | OperatedValve-1 | - | 오류 |
| n1 | n36 | OperatedValve-1 | - | 계측 신호선 |
| n13 | n14 | - | - | 계측 신호선 |
| n14 | n9 | - | - | 계측 신호선 |
| n15 | n16 | - | - | 계측 신호선 |
| n16 | n20 | - | - | 오류 |
| n28 | n30 | - | - | 계측 신호선 |
| n3 | n4 | ProcessInstrumentationFunction-1 | - | 계측 신호선 |
| n35 | n36 | - | - | 계측 신호선 |
| n6 | n7 | - | - | 계측 신호선 |
| n7 | n8 | - | - | 계측 신호선 |

## 라벨 소속

| 문자 | 정답 소속 종류 | 정답 대응 노드 | 추출 소속 | 일치 |
|---|---|---|---|---|
| ESV | ProcessInstrumentationFunction | n3 | n3 | O |
| 3712 | ProcessInstrumentationFunction | n3 | n3 | O |
