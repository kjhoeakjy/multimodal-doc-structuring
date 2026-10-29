# 표본 입력 묶음

화면(`app/`)과 처리 묶음이 다양한 입력을 받는지 확인하기 위한 20건. 도면·도해·표·보고서·사진을 섞었고 실제 자료와 합성 자료를 구분해 표기함.

## 구성

| 파일 | 종류 | 출처 |
|---|---|---|
| `pid-standard-vector.svg` | 표준 기호 P&ID, 벡터 | DEXPI 참조 예제 C01V04(공개) |
| `pid-plant-complex-vector.svg` | 증류 플랜트 P&ID, 장비 100개 이상, 벡터 | DEXPI 예제 distillation plant(공개) |
| `pid-lab-vector.svg` | 실험실 증류 P&ID, 벡터 | DEXPI 예제(공개) |
| `pid-standard-200dpi.png` | C01 200 dpi 래스터 | C01을 자체 변환기로 그림 |
| `pid-standard-scan.png` | C01 스캔 열화(0.4도 회전·잡음·JPEG) | 합성 열화 |
| `pid-plant-complex-150dpi.png` | 증류 플랜트 150 dpi 래스터(A1 크기) | 자체 변환 |
| `mech-flange-synthetic-vector.svg` | 기계 도면(플랜지: 원·호·치수선·지시선·표제란), 벡터 | 합성 |
| `mech-flange-synthetic-200dpi.png` | 같은 도면 200 dpi 래스터 | 합성 |
| `mech-iso-tolerance-real.jpg` | 치수·기하 공차 등각 도면, 곡선 다수 | NIST PMI 시험 모형 FTC 07(공개) |
| `faa-bolt-table-illustrations.jpg` | 행마다 삽화가 든 볼트 표 | FAA AC 43.13-1B 7장(공개, 약 100 dpi) |
| `faa-torque-table.jpg` | 토크 표, 행 구분선 없음 | FAA AC 43.13-1B(공개) |
| `faa-torque-table-scan.jpg` | 같은 표 200 dpi 스캔 | 합성 열화 |
| `faa-text-page.png` | 본문 위주 쪽(절 번호·문단, 2단) | FAA AC 43.13-1B(공개) |
| `ko-table-text-scan200.jpg` | 한글 본문 3문단·표 6행, 200 dpi 스캔 열화 | 합성 |
| `ko-report-synthetic.png` | 한글 보고서(제목·절·막대 그래프 그림·설명문·표) | 합성 |
| `en-report-synthetic-vector.pdf` | 영문 보고서 PDF(벡터 문자·표·선 그래프) | 합성 |
| `en-report-synthetic-scan150.jpg` | 같은 보고서 150 dpi 스캔 열화 | 합성 |
| `photo-rocket-launch.jpg` | 사진(발사대) | scikit-image 동봉 공개 사진 |
| `photo-astronaut.png` | 사진(인물) | scikit-image 동봉 공개 사진 |
| `photo-of-text-page.png` | 문서를 찍은 사진(작은 조각) | scikit-image 동봉 공개 사진 |

항공사·제조사 내부 문서는 공개본이 없어 포함하지 않음. 공개 항공 자료(FAA 교범, NTSB 보고서)는 외부망이 열린 환경에서 추가 예정.

## 처리 결과

`python run_all.py`로 전부 처리한 결과(`output/results.md`, 4코어 CPU, 스레드 2, 선택 설정 없음). 판별은 사람이 정한 종류와 20건 모두 일치함. 아래 표는 실행 시점의 기록이며 `output/<파일명>/`에 직렬화 텍스트(`*.txt`), 그래프(`graph.json`), 문자 인식 결과가 있음.

| 파일 | 판별 | 근거 | 해상도 | 문자 | 결과 | 시간 | 최대 메모리 |
|---|---|---|---|---|---|---|---|
| `en-report-synthetic-scan150.jpg` | 표 · 본문 쪽 | 문자 잉크 70%, 그 밖 잉크 5% | 150 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 34 | 표 1 · 그림 영역 2 · 문단 6 | 46.8초 | 4.37 GB |
| `en-report-synthetic-vector.pdf` | 벡터 도면 | PDF 벡터(경로 21개, 문자 있음) | - | 16 | 노드 6 · 간선 3 · 표 1 | 0.8초 | 1.0 GB |
| `faa-bolt-table-illustrations.jpg` | 표 · 본문 쪽 | 문자 잉크 47%, 그 밖 잉크 25% | 104 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 83 | 표 3 · 그림 영역 26 · 문단 3 | 20.6초 | 2.48 GB |
| `faa-text-page.jpg` | 표 · 본문 쪽 | 문자 잉크 67%, 그 밖 잉크 0% | 111 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 209 | 표 1 · 그림 영역 0 · 문단 3 | 31.3초 | 2.89 GB |
| `faa-torque-table-scan.jpg` | 표 · 본문 쪽 | 문자 잉크 73%, 그 밖 잉크 10% | 206 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 217 | 표 1 · 그림 영역 0 · 문단 3 | 55.7초 | 4.82 GB |
| `faa-torque-table.png` | 표 · 본문 쪽 | 문자 잉크 100%, 그 밖 잉크 0% | 104 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 72 | 표 0 · 그림 영역 0 · 문단 2 | 20.5초 | 2.54 GB |
| `ko-report-synthetic.png` | 표 · 본문 쪽 | 문자 잉크 47%, 그 밖 잉크 0% | 200 (파일 메타데이터) | 38 | 표 1 · 그림 영역 0 · 문단 5 | 39.2초 | 4.46 GB |
| `ko-table-text-scan200.jpg` | 표 · 본문 쪽 | 문자 잉크 68%, 그 밖 잉크 9% | 200 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 36 | 표 1 · 그림 영역 16 · 문단 5 | 40.6초 | 4.5 GB |
| `mech-flange-synthetic-200dpi.png` | 도해 · 기계 도면 | 문자 잉크 16%, 큰 원 4개, 긴 선 50개 | 200 (파일 메타데이터) | 19 | 주기 17 · 지시선 12 | 42.6초 | 4.34 GB |
| `mech-flange-synthetic-vector.svg` | 벡터 도면 | 벡터 SVG | - | 20 | 노드 54 · 간선 49 | 0.2초 | 1.16 GB |
| `mech-iso-tolerance-real.jpg` | 도해 · 기계 도면 | 문자 잉크 58%, 큰 원 0개, 긴 선 27개 | 206 (문자 높이 4.5 mm 가정과 A4 용지 일치) | 96 | 주기 19 · 지시선 9 | 45.1초 | 4.89 GB |
| `photo-astronaut.png` | 사진 | 연속 계조 비율이 높음 | 300 (파일 메타데이터) | 0 | 임베딩 대상 | 4.0초 | 1.5 GB |
| `photo-of-text-page.png` | 사진 | 연속 계조 비율이 높음 | 96 (사진, 해상도 미정(96 가정)) | 12 | 임베딩 대상 | 2.5초 | 1.16 GB |
| `photo-rocket-launch.jpg` | 사진 | 연속 계조 비율이 높음 | 96 (사진, 해상도 미정(96 가정)) | 0 | 임베딩 대상 | 4.3초 | 1.55 GB |
| `pid-lab-vector.svg` | 벡터 도면 | 벡터 SVG | - | 0 | 노드 104 · 간선 94 | 0.9초 | 1.19 GB |
| `pid-plant-complex-150dpi.png` | 래스터 도식 | 축 평행 긴 선 498개, 선 잉크 62% | 176 (문자 적음, A2 용지 150 dpi 근방 가정) | 0 | 노드 825 · 간선 542 | 102.9초 | 4.59 GB |
| `pid-plant-complex-vector.svg` | 벡터 도면 | 벡터 SVG | - | 0 | 노드 345 · 간선 290 | 5.6초 | 1.21 GB |
| `pid-standard-200dpi.png` | 래스터 도식 | 축 평행 긴 선 140개, 선 잉크 55% | 200 (문자 높이 4.5 mm 가정과 A3 용지 일치) | 104 | 노드 178 · 간선 120 · 표 5 | 59.3초 | 4.5 GB |
| `pid-standard-scan.png` | 래스터 도식 | 축 평행 긴 선 140개, 선 잉크 59% | 200 (문자 높이 4.5 mm 가정과 A3 용지 일치) | 106 | 노드 149 · 간선 141 · 표 5 | 78.0초 | 4.53 GB |
| `pid-standard-vector.svg` | 벡터 도면 | 벡터 SVG | - | 100 | 노드 75 · 간선 43 · 표 5 | 0.5초 | 1.17 GB |

래스터 도면 중 `pid-standard-200dpi.png`는 정답 대조에서 인접 쌍 11/25 복원(벡터 27/27). 복잡한 플랜트 래스터는 문자가 인식되지 않아 노드 수가 과다함. 자세한 원인은 [public-documents](../public-documents/README.md) 참조.

## 생성

| 파일 | 내용 |
|---|---|
| `make_samples.py` | 보유 자료 복사, 기계 도면 SVG·래스터, 한글 보고서, 영문 벡터 PDF와 스캔본 생성 |
| `run_all.py` | 전부 처리하고 `output/results.json`, `output/results.md` 작성. 파일명을 인자로 주면 일부만 다시 처리 |

## 확인된 한계

- 래스터 도면의 해상도는 문자 상자 높이와 표준 용지 크기로 추정함. 문자가 10개 미만인 큰 도면(A1 150 dpi)은 40% 안팎 오차.
- 복잡한 P&ID 래스터(A1, 17 MP)는 입력 상한(12 MP)으로 축소되어 작은 글자 인식이 되지 않음.
- 한글 모델은 영문 도면에 쓰면 복원율이 떨어지므로 큰 글자 표본에서 한글이 확인될 때만 섞어 씀.
- 사진은 구조 추출 없이 사진 위 문자와 임베딩 대상 영역만 기록함. 임베딩 가중치가 없는 환경에서는 "모델 없음"으로 표시됨.
