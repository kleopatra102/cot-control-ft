#!/usr/bin/env bash
cd "$(dirname "$0")/../.."
until grep -q STAGE_TRACES_DONE results/supervisor.log; do sleep 60; done
until ! pgrep -f '^bash scripts/gpu_supervisor.sh' >/dev/null; do sleep 10; done
FIRST_IDLE_MIN=0 nohup scripts/gpu_supervisor.sh results/unlearn/stage_phase2.sh > /dev/null 2>&1 &
echo "phase2 launched $(date)"
