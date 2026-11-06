#!/usr/bin/env bash
# Smoke test of Ilinca's Gemma RL trainer (scripts/hf_rl_train.py, TRL + Unsloth, branch ola/gemma-eval) on skynet4's
# RTX 5090 (32 GB; her recipe ran on an 80 GB H100): does GRPO on Gemma-4-31B fit, and how fast is a step?
#   --smoke: 2 RL steps of 2 prompts x 4 samples at 512 tokens. Lookup, 6 steps, the treated arm (our v2 within-family
#   B adapter, text-only copy), no notice (the model is not told what is banned), monitor t3_v2 with adaptive k (--adaptive-k, branch ola/adaptive-k), RL alone (--no-sft), as in her pilot config otherwise.
# Waits for the environment (.venv-rl) and for a free GPU (under 1.5 GB in use, 3 checks 5 min apart), logs GPU memory
# every 5 s to gpu_mem.csv. Shares the GPU politely (scripts/hidden_state/gpu_polite.sh): gives it back to another user
# or a `touch /tmp/gpu_please` request, and starts over when it is free again. Output: results/hidden_state_rl/smoke_lookup_treated/.
set -uo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD; IL=/home/ola/dev/ext/ilinca-stego-rl; PY=$IL/.venv-rl/bin/python; OUT=$REPO/results/hidden_state_rl/smoke_lookup_treated
ENVLOG=/tmp/claude-1011/-home-ola/0549adc2-59da-403e-8814-8506bf9bab6f/scratchpad/build_rl_env.log
export HF_HUB_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1
export TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu   # skynet4's /sbin/ldconfig -p segfaults; Triton would call it
source scripts/hidden_state/gpu_polite.sh
mkdir -p "$OUT"

until grep -q ENV_OK "$ENVLOG" 2>/dev/null; do
  grep -qi "error" "$ENVLOG" 2>/dev/null && { log "environment build failed (see $ENVLOG)"; exit 3; }; sleep 60; done
log "environment ready"

while true; do
  wait_free
  nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader -l 5 > "$OUT/gpu_mem.csv" &
  MON=$!
  log "smoke test start"
  (cd "$IL" && run_watched "$PY" scripts/hf_rl_train.py --task lookup --arm treated \
    --adapter "$REPO/results/v2_gemma/ckpts/B/step-final-text" --base-model unsloth/gemma-4-31B-it-qat-q4_0-unquantized \
    --notice none --answer-format strict --monitor banned:lookup.t3_v2 --monitor-reply --n-steps 6 --seed 0 \
    --max-seq 4608 --micro-batch 4 --gpu-mem 0.6 --reasoning-format gemma4 --text-only --no-sft --adaptive-k --smoke \
    --log-dir "$OUT" > "$OUT/train.out" 2>&1)
  rc=$?
  kill $MON 2>/dev/null
  (( rc == 75 )) || break
  log "paused for another user; waiting for the GPU to be free again"; rm -rf "$OUT/checkpoints"; sleep 60
done
peak=$(awk -F', ' '{gsub(/ MiB/,"",$2); if ($2>m) m=$2} END {print m}' "$OUT/gpu_mem.csv")
log "smoke test exit $rc; peak GPU memory ${peak} MiB (of 32607)"
