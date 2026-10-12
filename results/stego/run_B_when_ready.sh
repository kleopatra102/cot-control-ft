#!/usr/bin/env bash
# Waits for B's Tinker checkpoint (results/v2_qwen38 stage), then runs the stego eval on it.
cd "$(dirname "$0")/../.."
C=results/v2_qwen38/qwen38_tinker/ckpt_B.json
until [[ -f $C ]]; do sleep 60; done
P=$(.venv-tinker/bin/python -c "import json; print(json.load(open('$C'))['sampler_path'])")
echo "[$(date '+%m-%d %H:%M')] checkpoint ready: $P"
.venv-tinker/bin/python scripts/stego/run.py --label B --model-path "$P"
echo STEGO_B_DONE
