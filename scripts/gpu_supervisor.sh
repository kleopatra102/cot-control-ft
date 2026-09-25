#!/usr/bin/env bash
# Run a GPU stage under a supervisor that yields the card to colleagues.
#
#   scripts/gpu_supervisor.sh <stage-script>
#
# The stage script must be idempotent/resumable: it is (re)started from scratch after every pause.
# It should start the vLLM server itself (scripts/serve_vllm.sh) and exit when its work is done.
#
# Pause triggers, checked every 5 s:
#   * the file /tmp/pause_ola exists            (a colleague: `touch /tmp/pause_ola`; remove to resume)
#   * another user's process holding > 2 GB of GPU memory (automatic yield; their first load may still fail)
# On a trigger the stage and every vllm/python child are killed. The stage restarts when no trigger
# is active and GPU memory has been below 8 GB for IDLE_MIN minutes (default 10).
#
# Logs: results/supervisor.log. Stop the supervisor itself with: touch /tmp/stop_ola_supervisor
set -uo pipefail
cd "$(dirname "$0")/.."
STAGE="$1"; IDLE_MIN="${IDLE_MIN:-10}"; FIRST_IDLE_MIN="${FIRST_IDLE_MIN:-0}"; first=1
LOG=results/supervisor.log
PAUSE=/tmp/pause_ola; STOP=/tmp/stop_ola_supervisor
log() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

trigger() {
  [[ -e "$PAUSE" ]] && { echo "pause file"; return 0; }
  # a process of another user holding > 2 GB (the colleague's llama-server keeps ~0.6 GB while asleep)
  while IFS=, read -r pid mem; do
    pid=$(echo "$pid" | tr -d ' '); mem=$(echo "$mem" | tr -d ' ')
    [[ -z "$pid" ]] && continue
    owner=$(ps -o user= -p "$pid" 2>/dev/null)
    if [[ -n "$owner" && "$owner" != "$(id -un)" && "$mem" -gt 2000 ]]; then echo "colleague process $pid using ${mem} MiB"; return 0; fi
  done < <(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits)
  return 1
}
gpu_used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1; }

kill_stage() {
  if [[ -n "${STAGE_PID:-}" ]] && kill -0 "$STAGE_PID" 2>/dev/null; then
    pkill -TERM -P "$STAGE_PID" 2>/dev/null; kill -TERM "$STAGE_PID" 2>/dev/null
  fi
  # anchored patterns: only real server / job processes, never a shell whose command line mentions them
  for p in $(pgrep -f '^[^ ]*/bin/(python[0-9.]*|vllm) ([^ ]*/bin/vllm )?serve ' ; pgrep -f '^[^ ]*/bin/python[0-9.]* scripts/(calibrate_number_words|build_sft|run_multi_eval|run_baseline|train_lora)\.py'); do kill -TERM "$p" 2>/dev/null; done
  sleep 5
  for p in $(pgrep -f '^[^ ]*/bin/(python[0-9.]*|vllm) ([^ ]*/bin/vllm )?serve '); do kill -KILL "$p" 2>/dev/null; done
  STAGE_PID=""
}

while true; do
  [[ -e "$STOP" ]] && { log "stop requested"; kill_stage; rm -f "$STOP"; exit 0; }
  if [[ -z "${STAGE_PID:-}" ]]; then
    # wait until no trigger and GPU idle for IDLE_MIN minutes
    idle=0
    while true; do
      [[ -e "$STOP" ]] && { log "stop requested"; rm -f "$STOP"; exit 0; }
      if t=$(trigger); then idle=0; sleep 30; continue; fi
      if [[ "$(gpu_used)" -lt 8000 ]]; then idle=$((idle+1)); else idle=0; fi
      need=$IDLE_MIN; [[ $first -eq 1 ]] && need=$FIRST_IDLE_MIN
      [[ $idle -ge $((need*2)) ]] && break
      sleep 30
    done
    log "starting stage: $STAGE"
    bash "$STAGE" >> "$LOG" 2>&1 &
    STAGE_PID=$!; first=0
  fi
  if t=$(trigger); then
    log "yielding GPU ($t)"; kill_stage; continue
  fi
  if ! kill -0 "$STAGE_PID" 2>/dev/null; then
    wait "$STAGE_PID"; rc=$?
    log "stage exited rc=$rc"
    [[ $rc -eq 0 ]] && exit 0
    STAGE_PID=""; sleep 60
  fi
  sleep 5
done
