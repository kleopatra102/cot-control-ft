#!/usr/bin/env bash
# Queue (2026-10-04): wait for the gpt-oss v2 stage to finish, write its report, wait for the Gemma downloads,
# then run the Gemma v2 stage under the GPU supervisor. Log: results/v2_gemma/queue.log
cd "$(dirname "$0")/../.."
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
log "waiting for the gpt-oss stage"
while pgrep -f "^/bin/bash scripts/gpu_supervisor.sh results/v2_gptoss/stage.sh|^bash scripts/gpu_supervisor.sh results/v2_gptoss/stage.sh" >/dev/null; do sleep 60; done
log "gpt-oss stage finished"; V2_RUN=gptoss .venv/bin/python scripts/v2/report.py > results/v2_gptoss/report.log 2>&1; tail -8 results/v2_gptoss/report.log
log "waiting for the Gemma downloads"
while pgrep -f "^.venv/bin/hf download|hf download google/gemma|hf download unsloth/gemma" >/dev/null; do sleep 60; done
tail -c 400 results/v2_gemma/download.log | tr '\r' '\n' | tail -2
log "starting the Gemma stage"
scripts/gpu_supervisor.sh results/v2_gemma/stage.sh
log "queue done"
