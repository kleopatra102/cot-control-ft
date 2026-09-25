#!/usr/bin/env bash
# Waits for the source stage, then starts the CPU build and the supervised GPU main stage.
cd "$(dirname "$0")/../.."
until grep -q STAGE_SOURCE_DONE results/supervisor.log; do sleep 60; done
until ! pgrep -f 'gpu_supervisor.sh results' >/dev/null; do sleep 10; done
nohup results/qwen3_8b/stage_build.sh > results/qwen3_8b/build.log 2>&1 &
FIRST_IDLE_MIN=0 nohup scripts/gpu_supervisor.sh results/qwen3_8b/stage_main.sh > /dev/null 2>&1 &
echo "launched $(date)"
