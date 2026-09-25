#!/usr/bin/env bash
# CPU stage: build the six Qwen3-8B training sets with the editor (gpt-4.1-mini, T=0). Idempotent.
set -uo pipefail
cd "$(dirname "$0")/../.."
for arm in S1 P2 T3 Q4 Q5 M5; do
  out=data/sft/q3_8b_${arm}.jsonl
  if [[ -s $out ]]; then echo "build: $arm exists"; continue; fi
  echo "build: $arm $(date +%H:%M)"
  .venv/bin/python scripts/build_sft_multi.py --arm $arm --rollouts results/qwen3_8b/sft/stage1_rollouts.jsonl --out-dir results/qwen3_8b/multi --data-prefix q3_8b --n-rows 920 > results/qwen3_8b/build_${arm}.log 2>&1 || { echo "build: $arm FAILED"; tail -3 results/qwen3_8b/build_${arm}.log; }
  tail -1 results/qwen3_8b/build_${arm}.log
done
ls -la data/sft/q3_8b_*.jsonl | awk '{print $5, $9}'
echo BUILD_DONE
