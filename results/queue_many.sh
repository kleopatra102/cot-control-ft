#!/usr/bin/env bash
# Queue: gpt-oss-20b many-rule arms, then DeepSeek-R1-Distill-Llama-8B (base, Q5, A, B). Each stage is idempotent.
cd "$(dirname "$0")/.."
results/gptoss_many/stage.sh || exit $?
results/r1llama/stage.sh || exit $?
echo QUEUE_MANY_DONE
