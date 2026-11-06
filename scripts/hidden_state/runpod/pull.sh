#!/usr/bin/env bash
# Run on skynet4: copy a pod's run folders back (no checkpoints' optimizer states needed later; adapters are kept).
# Usage: pull.sh <ssh-host> <ssh-port>   -> results/hidden_state_rl/runpod/
set -euo pipefail
HOST=$1 PORT=$2; OUT=/home/ola/dev/cot-control-ft/results/hidden_state_rl/runpod
mkdir -p "$OUT"
rsync -a --info=progress2 --exclude 'optimizer.pt' -e "ssh -p $PORT" "$HOST:/workspace/ilinca-stego-rl/runs/" "$OUT/"
rsync -a -e "ssh -p $PORT" "$HOST:/workspace/run_*.log" "$OUT/" 2>/dev/null || true
echo "pulled to $OUT"
