# 파인튜닝 축(가중치 지렛대) 파일럿

연구 설계 v3 §4.5. 질문: 구조화 오류의 영향 가운데 파인튜닝이 흡수할 수 있는 부분은 무엇인가. 비교는 2×2(입력 full/paths × 가중치 기본/LoRA)이며 같은 C01 설정·문항(noise/contexts.json)으로 잰다.

원칙
- 학습 자료는 공개 자료만 쓴다(PID2Graph Dataset PID의 위상 + 합성 문자, DEXPI C02). 회사 자료는 쓰지 않는다.
- C01은 평가 전용이며 학습에 넣지 않는다(도면 단위 분리). C03 벡터 추출 그래프는 문자가 거의 없어 평가 대상에서 뺀다.
- 학습은 빌린 GPU(vast.ai 등)에서 하고, 논문에는 연구 학습이 공개 자료·임대 GPU로 이루어졌고 운용 가정은 사내 GPU임을 적는다.

파일
| 파일 | 역할 | 실행 위치 |
|---|---|---|
| synth_graph.py | PID2Graph graphml → graph.json(합성 태그·접속구·계기 번호·라인 라벨) | CPU(노트북, graphml이 있는 곳) |
| qgen.py | graph.json만으로 문항·답 생성(기존 문항 형식 11종 + '자료에 없음') | CPU |
| make_train.py | 태그 치환 사본, 오류 주입(noise.py), 직렬화, full/paths 문맥, 대화 JSONL | CPU |
| train_lora.py | 8B LoRA SFT(assistant 부분에만 손실) | GPU |
| eval_lora.py | run_noise.py와 같은 설정·문항·채점으로 결과 jsonl·md 생성 | GPU |
| subsample.py | 큰 학습 자료에서 파일럿용 무작위 표본(기본 8,000개) | CPU |
| run.sh | 학습 → 기본/LoRA × noise/conn 평가 4회 | GPU |

순서
```
# 노트북(CPU)
python finetune/synth_graph.py "C:\data\PID2Graph\Complete\Dataset PID" finetune/synth --limit 200
python finetune/make_train.py --graphs finetune/synth docs/pid-c02-vector/graph.json --retag 2 --noise mixed --out finetune/train.jsonl
python finetune/subsample.py finetune/train.jsonl finetune/train-8k.jsonl --n 8000      # 2026-11-04 생성분은 82,002예시·1.05 GB라 파일럿은 8,000개로
# 빌린 GPU
MODEL=<HF 8B instruct 모델 id> bash finetune/run.sh finetune/train-8k.jsonl     # VRAM 12 GB면 Q4=1 를 앞에 붙임. 8B 실험과 같은 모델(llama3.1 8B instruct)을 씀
```
결과는 results/open-8b-hf-<TAG>-noise·conn.md(기본 가중치, HF 실행)와 results/open-8b-lora-<TAG>-noise·conn.md. 기본 가중치도 같은 코드로 다시 재므로 Ollama 양자화 결과와 섞이지 않는다.

학습 자료의 답은 문맥을 만든 그래프(오류가 들어간 뒤)에서 계산한다. 따라서 모델이 배우는 것은 주어진 자료를 형식대로 읽고 연결을 따라가는 일이며, 자료에서 사라진 문자나 귀속을 되살리는 일이 아니다. 이것이 파인튜닝 축의 가설(형식 적응·연결 추적은 오르고, 근거 손실은 회복되지 않음)과 맞는다.

판정: 대표 설정 12개에서 LoRA가 연결 문항(questions-conn.json) 정답률을 기본 가중치보다 의미 있게 올리면 본 실험(모델 사다리 전체)에 넣고, 아니면 Q1~Q4로 투고하고 후속 과제로 둔다.

검증: train_lora.py·eval_lora.py는 무작위 초기화한 2층 소형 모형과 예시 40개로 CPU에서 끝까지 실행됨을 확인함(transformers 5.x). 8B·GPU에서 첫 실행 시 메모리 부족이면 `--4bit`(run.sh는 `Q4=1`) 또는 `--max-len 4096`.
