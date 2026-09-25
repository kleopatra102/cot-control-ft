#!/usr/bin/env bash
# Stage 1 for Qwen3-8B: number_words calibration + unconstrained source rollouts. Resumable.
set -uo pipefail
cd "$(dirname "$0")/../.."
MODEL=Qwen/Qwen3-8B KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN scripts/serve_vllm.sh > results/qwen3_8b/serve.log 2>&1 &
SERVER=$!
until grep -qE "Application startup complete" results/qwen3_8b/serve.log; do kill -0 $SERVER 2>/dev/null || exit 2; sleep 5; done
.venv/bin/python scripts/calibrate_number_words.py --model Qwen/Qwen3-8B --out-dir results/qwen3_8b/calibration >> results/qwen3_8b/calibration.log 2>&1 &
A=$!
.venv/bin/python scripts/build_sft.py --stage 1 --model Qwen/Qwen3-8B --out-dir results/qwen3_8b/sft >> results/qwen3_8b/stage1.log 2>&1 &
B=$!
wait $A; ra=$?; wait $B; rb=$?
kill $SERVER 2>/dev/null; sleep 5
[[ $ra -eq 0 && $rb -eq 0 ]] && { echo STAGE_SOURCE_DONE; exit 0; }
exit 1
