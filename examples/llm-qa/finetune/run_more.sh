#!/usr/bin/env bash
# 논문 보강 평가를 빌린 GPU에서 한 번에 돌림: 씨앗 1·2 추가(기본·LoRA·14B)와 미학습 도면(OPEN100). 재학습 없음.
# 준비: 저장소 복제, 어댑터 압축을 /workspace/adapter.tgz로 올림, 환경 변수 HF_TOKEN. 디스크 60GB 이상.
# 사용: cd examples/llm-qa && bash finetune/run_more.sh
# 끝나면 /workspace/more-results.tgz 하나만 내려받으면 됨. 같은 명령을 다시 실행하면 끝난 호출은 건너뜀.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONUTF8=1
MODEL=${MODEL:-meta-llama/Llama-3.1-8B-Instruct}; TAG=${TAG:-2026-11}
RX='^(drop-0\.[25]|add-0\.5|ocr-0\.[25]|attr-0\.[25]|mix-0\.[25])-'
pip install -q -r finetune/requirements.txt || exit 1
[ -f finetune/adapter/adapter_model.safetensors ] || tar xzf /workspace/adapter.tgz -C . || exit 1
[ -f finetune/adapter/adapter_model.safetensors ] || { echo "어댑터 없음"; exit 1; }
command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
export OLLAMA_MODELS=/workspace/ollama
curl -s -m 3 -o /dev/null http://127.0.0.1:11434/api/tags || { nohup ollama serve > /workspace/ollama.log 2>&1 & sleep 5; }
ollama pull phi4:14b || exit 1
ollama pull llama3.1:8b || exit 1

for Q in questions-conn.json ""; do
  SUF=$([ -z "$Q" ] && echo noise || echo conn)
  python run_noise.py --backend ollama --model phi4:14b --label "open-14b-$TAG-$SUF" --seeds 1,2 --conds full --settings "$RX" ${Q:+--qfile $Q}
done
python run_noise.py --backend ollama --model llama3.1:8b --label "open-8b-$TAG-paths" --seeds 1,2 --conds paths --settings "$RX" --qfile questions-conn.json
for M in hf lora; do
  A=$([ $M = lora ] && echo "--adapter finetune/adapter")
  python finetune/eval_holdout.py --backend hf --model "$MODEL" $A --label "open-8b-$M-$TAG-holdout"
  for Q in questions-conn.json ""; do
    SUF=$([ -z "$Q" ] && echo noise || echo conn)
    python finetune/eval_lora.py --model "$MODEL" $A --label "open-8b-$M-$TAG-$SUF" --seeds 1,2 --conds full,paths --settings "$RX" ${Q:+--qfile $Q}
  done
done
python finetune/eval_holdout.py --backend ollama --model phi4:14b --label "open-14b-$TAG-holdout"
tar czf /workspace/more-results.tgz results/open-14b-$TAG-* results/open-8b-hf-$TAG-* results/open-8b-lora-$TAG-* results/open-8b-$TAG-paths.*
ls -lh /workspace/more-results.tgz
echo "완료: /workspace/more-results.tgz"
