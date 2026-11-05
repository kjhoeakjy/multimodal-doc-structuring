#!/usr/bin/env bash
# 씨앗 추가 실행(빌린 GPU). 씨앗 0만 있는 결과(14B, 8B paths, 기본·LoRA 2×2)에 씨앗 1·2를 같은 결과 이름으로 이어 붙인다.
# 결과 파일은 이미 저장소에 있으므로 실행 전 git pull로 받아 두면 남은 호출만 돈다(씨앗 0은 다시 묻지 않음).
# 사용: bash run_seeds.sh ollama   # 1부: Ollama(14B noise·conn, 8B paths), OLLAMA_MODELS=/workspace/ollama 로 서버가 떠 있어야 함
#       bash run_seeds.sh hf       # 2부: HF(기본·LoRA 2×2), MODEL·HF_TOKEN 환경 변수와 finetune/adapter 필요. 디스크가 좁으면 1부 뒤 Ollama 모델을 지우고 실행
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
S='^(none|drop|ocr|attr|mix)-(0|0.2|0.5)-|^add-0.5|^real'
case "${1:-}" in
  ollama)
    python run_noise.py --backend ollama --model phi4:14b --label open-14b-2026-11-noise --conds full --seeds 0,1,2 --settings "$S"
    python run_noise.py --backend ollama --model phi4:14b --label open-14b-2026-11-conn --conds full --seeds 0,1,2 --settings "$S" --qfile questions-conn.json
    python run_noise.py --backend ollama --model llama3.1:8b --label open-8b-2026-11-paths --conds paths --seeds 0,1,2 --settings "$S" --qfile questions-conn.json
    ;;
  hf)
    MODEL=${MODEL:?HF 모델 id 필요}
    for Q in "" questions-conn.json; do
      SUF=$([ -z "$Q" ] && echo noise || echo conn)
      python finetune/eval_lora.py --model "$MODEL" --label "open-8b-hf-2026-11-$SUF" --conds full,paths --seeds 0,1,2 --settings "$S" ${Q:+--qfile $Q}
      python finetune/eval_lora.py --model "$MODEL" --adapter finetune/adapter --label "open-8b-lora-2026-11-$SUF" --conds full,paths --seeds 0,1,2 --settings "$S" ${Q:+--qfile $Q}
    done
    ;;
  *) echo "사용: bash run_seeds.sh ollama|hf"; exit 1;;
esac
for L in open-14b-2026-11-noise open-14b-2026-11-conn open-8b-hf-2026-11-noise open-8b-lora-2026-11-noise open-8b-hf-2026-11-conn open-8b-lora-2026-11-conn; do
  [ -f "results/$L.jsonl" ] && python intervals.py --label "$L" || true
done
[ -f results/open-8b-2026-11-paths.jsonl ] && python intervals.py --label open-8b-2026-11-paths --cond paths || true
