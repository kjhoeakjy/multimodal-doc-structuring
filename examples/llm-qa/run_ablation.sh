#!/usr/bin/env bash
# 입력 조건 분리 실험(로컬 Ollama, CPU). 같은 추출 결과에서 관계 줄을 단계적으로 더한 다섯 조건을 같은 모델로 비교함.
#   ocr, objects(요소·속성 목록), relations(요소와 연결), full(연결과 장비 간 도달), retrieved(질문 문장 기준 부분 그래프)
# 사용: bash run_ablation.sh [ollama 모델 이름, 기본 llama3.1:8b] [이전 결과 이름(같은 문맥 응답 재사용), 기본 open-8b-2026-10-all]
set -euo pipefail
cd "$(dirname "$0")"
MODEL=${1:-llama3.1:8b}
SEED=${2:-open-8b-2026-10-all}
size=$(echo "$MODEL" | grep -oE '[0-9]+b' | head -1 || true)
LABEL="open-${size:-x}-$(date +%Y-%m)-abl"
python contexts.py
[ -f "results/$LABEL.jsonl" ] || [ ! -f "results/$SEED.jsonl" ] || python seed_results.py "$SEED" "$LABEL"
python run_qa.py --backend ollama --model "$MODEL" --label "$LABEL" --conds ocr,objects,relations,full,retrieved
python select_repr.py "$LABEL"
