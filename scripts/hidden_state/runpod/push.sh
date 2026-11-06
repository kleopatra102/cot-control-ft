#!/usr/bin/env bash
# Run on skynet4: copy Ilinca's repo at branch ola/gemma-rl-nonotice (code only, no venvs) and our v2 within-family Gemma
# LoRA (text-only key names) to a RunPod pod, plus pod_run.sh. Usage: push.sh <ssh-host> <ssh-port>
# (RunPod: pod page -> Connect -> "SSH over exposed TCP", e.g. root@203.0.113.7 -p 22101).
set -euo pipefail
HOST=$1 PORT=$2; SSH=(ssh -p "$PORT" -o StrictHostKeyChecking=accept-new "$HOST")
IL=/home/ola/dev/ext/ilinca-stego-rl; ADAPTER=/home/ola/dev/cot-control-ft/results/v2_gemma/ckpts/B/step-final-text
"${SSH[@]}" "mkdir -p /workspace/ilinca-stego-rl /workspace/treated-adapters"
git -C "$IL" archive --format=tar origin/ola/gemma-rl-nonotice | "${SSH[@]}" "tar -x -C /workspace/ilinca-stego-rl"
rsync -a --info=progress2 -e "ssh -p $PORT" "$ADAPTER/" "$HOST:/workspace/treated-adapters/gemma-4-31b-v2-within-family-text/"
rsync -a -e "ssh -p $PORT" "$(dirname "$0")/pod_run.sh" "$HOST:/workspace/pod_run.sh"
echo "pushed; on the pod: ARM=cotctl bash /workspace/pod_run.sh   (or ARM=base; SMOKE=1 for a 2-step check first)"
