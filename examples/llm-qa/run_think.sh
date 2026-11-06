#!/usr/bin/env bash
# 사고 기능이 있는 공개 가중치 8B 모델을 같은 모델로 사고 끔·켬 두 조건에서 평가(대표 12설정, 씨앗 0).
# 연결 36문항 full·paths, 일반 43문항 full. 사고 끔이 빨라 먼저 실행함. 결과는 results/open-8b-think-*, open-8b-nothink-*.
# 사용: cd examples/llm-qa && bash run_think.sh   (Ollama 0.9 이상 실행 중, 모델은 자동 내려받음)
set -uo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
MODEL=${MODEL:-qwen3:8b}
RX='^(none|drop-0\.[25]|add-0\.5|ocr-0\.[25]|attr-0\.[25]|mix-0\.[25]|real)'
ollama pull "$MODEL" || exit 1
export OLLAMA_EXTRA='{"think": false}'
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-nothink-2026-11-conn  --qfile questions-conn.json --seeds 0 --conds full  --settings "$RX"
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-nothink-2026-11-paths --qfile questions-conn.json --seeds 0 --conds paths --settings "$RX"
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-nothink-2026-11-noise --seeds 0 --conds full --settings "$RX"
export OLLAMA_EXTRA='{"think": true, "options": {"num_predict": 4000}}'
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-think-2026-11-conn  --qfile questions-conn.json --seeds 0 --conds full  --settings "$RX"
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-think-2026-11-paths --qfile questions-conn.json --seeds 0 --conds paths --settings "$RX"
python run_noise.py --backend ollama --model "$MODEL" --label open-8b-think-2026-11-noise --seeds 0 --conds full --settings "$RX"
for f in results/open-8b-think-2026-11-*.jsonl results/open-8b-nothink-2026-11-*.jsonl; do echo "$f $(wc -l < "$f")"; done
tar czf /workspace/think-results.tgz results/open-8b-think-2026-11-* results/open-8b-nothink-2026-11-* && echo "완료: /workspace/think-results.tgz"
