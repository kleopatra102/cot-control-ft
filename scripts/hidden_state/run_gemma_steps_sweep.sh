#!/usr/bin/env bash
# At how many steps does each hidden-state task need a CoT? Gemma-4-31B base and our v2 B, accuracy with and without
# reasoning at 12, 20 and 30 steps (6 steps: results/hidden_state). RL only teaches covert reasoning where the
# no-reasoning accuracy is near chance (coin 50 %, direction 25 %, lookup 10 %) and the with-reasoning accuracy is high.
#   conditions: nothink (reasoning off) and think (reasoning on); no notice, no monitor pressure; 4,096 tokens (the RL
#   recipe's cap, so a CoT that needs more than that is visible as truncation)
#   40 held-out instances x 4 samples per cell; 3 tasks x 3 step counts x 2 arms x 2 conditions = 36 cells
# Then runs the RL smoke test (scripts/hidden_state/run_gemma_rl_smoke.sh). Shares the GPU politely
# (scripts/hidden_state/gpu_polite.sh): starts only when it is free, gives it back as soon as another user starts a GPU
# process or runs `touch /tmp/gpu_please`, and resumes from the unfinished cell when it is free again. Serves on port
# 8011; stops only its own server. Idempotent per cell (a stopped cell has written nothing and re-runs).
set -uo pipefail
cd "$(dirname "$0")/../.."
REPO=$PWD; IL=/home/ola/dev/ext/ilinca-stego-rl; PY=$IL/.venv/bin/python; OUT=$REPO/results/hidden_state_steps
export HF_HUB_OFFLINE=1 ENDPOINT_API_KEY=EMPTY PORT=8011
export TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu   # skynet4's /sbin/ldconfig -p segfaults; Triton would call it
source scripts/hidden_state/gpu_polite.sh
mkdir -p "$OUT"

declare -A SERVED=([base]=google/gemma-4-31B-it-qat-w4a16-ct [treated]=v2g-B)
COMMON=(--base-url http://localhost:$PORT/v1 --model-name google/gemma-4-31B-it-qat-w4a16-ct --answer-format strict
        --notice none --n 40 --samples 4 --max-tokens 4096 --temperature 1.0 --concurrency 16)

run_cells() {  # returns 75 when it gave the GPU back
  local cond steps task arm d rc; local -a X
  for cond in nothink think; do            # the fast no-reasoning cells first
    for steps in 12 20 30; do
      for task in lookup direction coinflip; do
        for arm in base treated; do
          d="$OUT/$task/s$steps/$arm/$cond"; [[ -f $d/samples_summary.jsonl ]] && continue; mkdir -p "$(dirname "$d")"
          X=(); [[ $cond == nothink ]] && X=(--no-thinking)
          log "eval $task steps=$steps $arm $cond"
          run_watched "$PY" "$IL/scripts/hidden_state_endpoint_eval.py" --task "$task" --n-steps "$steps" \
            --served-model "${SERVED[$arm]}" --label "$arm" "${COMMON[@]}" --log-dir "$d" "${X[@]}" > "$d.log" 2>&1
          rc=$?; (( rc == 75 )) && return 75; (( rc )) && log "FAILED $task $steps $arm $cond (see $d.log)"
          grep -h "^summary" "$d.log" | grep -o '"label/correct": [0-9.]*\|"truncated": [0-9.]*\|"reasoning_words": [0-9.]*' | tr '\n' ' '; echo
        done
      done
    done
  done
}

while true; do
  wait_free
  log "serve base + v2g-B"
  setsid scripts/stego/serve_gemma.sh > "$OUT/serve.log" 2>&1 < /dev/null & SERVER=$!
  rc=0
  until curl -s localhost:$PORT/v1/models | grep -q v2g-B; do
    grep -q "Engine core initialization failed" "$OUT/serve.log" && { log "vLLM failed to start"; kill_group $SERVER; exit 4; }
    if why=$(someone_else); then log "giving the GPU back: $why"; rc=75; break; fi
    sleep 10
  done
  (( rc == 0 )) && { run_cells; rc=$?; }
  kill_group $SERVER; wait $SERVER 2>/dev/null
  (( rc == 75 )) || break
  log "paused for another user; waiting for the GPU to be free again"; sleep 60
done
log "sweep done"
sleep 60   # let the server release the GPU
exec scripts/hidden_state/run_gemma_rl_smoke.sh
