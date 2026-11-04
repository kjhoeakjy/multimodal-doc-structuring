#!/usr/bin/env bash
# 빌린 GPU(vast.ai 등)에서 8B LoRA 파일럿을 한 번에 돌림. 학습 자료(train.jsonl)는 노트북에서 make_train.py로 만들어 올린다(공개 자료만).
# 사용: MODEL=<HF 모델 id> bash run.sh train.jsonl
#   HF 접근 토큰은 환경 변수 HF_TOKEN. 결과는 ../results/open-8b-hf-* (기본 가중치) 와 ../results/open-8b-lora-* (LoRA).
set -euo pipefail
cd "$(dirname "$0")"
DATA=${1:-train.jsonl}; MODEL=${MODEL:?HF 모델 id 필요}; TAG=${TAG:-2026-11}
SET=${SETTINGS:-'^(none|drop|ocr|attr|mix)-(0|0.2|0.5)-|^add-0.5|^real'}     # 대표 설정 12개
pip install -q -r requirements.txt
python train_lora.py --data "$DATA" --model "$MODEL" --out adapter --epochs "${EPOCHS:-2}" ${Q4:+--4bit}
for Q in "" questions-conn.json; do
  SUF=$([ -z "$Q" ] && echo noise || echo conn)
  python eval_lora.py --model "$MODEL" --label "open-8b-hf-$TAG-$SUF" --conds full,paths --settings "$SET" ${Q:+--qfile $Q} ${Q4:+--4bit}
  python eval_lora.py --model "$MODEL" --adapter adapter --label "open-8b-lora-$TAG-$SUF" --conds full,paths --settings "$SET" ${Q:+--qfile $Q} ${Q4:+--4bit}
done
echo "완료: ../results/open-8b-hf-$TAG-*.md, open-8b-lora-$TAG-*.md"
