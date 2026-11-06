#!/usr/bin/env bash
# Run on the RunPod pod after push.sh: set up the pinned environment (scripts/pod/bootstrap_rl.sh: venv, the Gemma
# training base and the quantized serving base, ~110 GB under /workspace) once, then launch one arm of
# configs/gemma4-31b/lookup/rl/gemma4-31b_lookup_rl.toml: RL (60 steps), then the test curve of every saved checkpoint.
#   ARM=cotctl|base  [SMOKE=1: rl.steps=2, to check memory and speed first]  bash /workspace/pod_run.sh
# Runs under nohup; log /workspace/run_<arm>.log; results under /workspace/ilinca-stego-rl/runs/.
set -euo pipefail
: "${ARM:?ARM=cotctl or ARM=base}"
cd /workspace/ilinca-stego-rl
[ -f /workspace/rl-env.sh ] || WORKSPACE=/workspace bash scripts/pod/bootstrap_rl.sh 2>&1 | tee /workspace/bootstrap.log
source /workspace/rl-env.sh
EXTRA=(); [ "${SMOKE:-0}" = 1 ] && EXTRA=(--set rl.steps=2)
nohup python scripts/run_experiment.py configs/gemma4-31b/lookup/rl/gemma4-31b_lookup_rl.toml --arm "$ARM" --seed 0 \
  --local-checkpoint gemma4-31b-cotctl-v2-within-family=/workspace/treated-adapters/gemma-4-31b-v2-within-family-text \
  --local-checkpoint google/gemma-4-31B-it-qat-w4a16-ct=/workspace/models/gemma-base "${EXTRA[@]}" --run \
  > "/workspace/run_${ARM}.log" 2>&1 &
echo "started $ARM (pid $!); follow: tail -f /workspace/run_${ARM}.log"
