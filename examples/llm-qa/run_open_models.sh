#!/usr/bin/env bash
# 공개 가중치 모델 비교군 실행(로컬 Ollama, 폐쇄망·제한 GPU 가정).
# 사용: bash run_open_models.sh [ollama 모델 이름 ...]
# 인수가 없으면 아래 기본 세 모델(8B·7B·14B급 지시 모델)을 차례로 실행함. 결과 이름은 규모와 시점만 적음.
set -euo pipefail
cd "$(dirname "$0")"
MODELS=("$@")
if [ ${#MODELS[@]} -eq 0 ]; then
  MODELS=(llama3.1:8b mistral:7b phi4:14b)
fi
STAMP=$(date +%Y-%m)
for m in "${MODELS[@]}"; do
  size=$(echo "$m" | grep -oE '[0-9]+b' | head -1 || true)
  label="open-${size:-x}-${STAMP}"
  echo "== $m -> results/$label"
  ollama pull "$m"
  python run_qa.py --backend ollama --model "$m" --label "$label"
  python analyze.py "$label"
done
