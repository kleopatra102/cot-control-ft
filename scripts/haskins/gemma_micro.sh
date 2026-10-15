#!/usr/bin/env bash
# Short Haskins et al. run on Gemma-4-31B B (v2 within-family adapter), local GPU. Haskins' original prompt (Gemma B
# reasons on it in 40/40). Stage 1: 300 behavioural docs, lr 1e-4, 1 epoch, continuing B's adapter; MA: 300 monitoring
# docs, lr 1e-5, 1 epoch, from stage 1. Eval on 200 scenarios (110 with a defect): stage 1 (control) and MA, MA with
# thinking off; monitor + counterfactual autorater. Idempotent.
set -euo pipefail
cd "$(dirname "$0")/../.."
G=results/haskins/gemma; C=$G/ckpts; D=$G/data; PYU=.venv-unsloth/bin/python; PYT=.venv-tinker/bin/python
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
stop_vllm() { pkill -f "vllm serve" 2>/dev/null || true; for _ in $(seq 60); do nvidia-smi --query-compute-apps=pid --format=csv,noheader | grep -q . || return 0; sleep 5; done; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1
.venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('unsloth/gemma-4-31B-it-qat-q4_0-unquantized', local_files_only=True)"
stop_vllm
[[ -f $C/s1/step-final/adapter_config.json ]] || { log "train s1"; $PYU scripts/haskins/train_sdf_gemma.py --data $D/behav1/train.jsonl --init-adapter results/v2_gemma/ckpts/B/step-final --out-dir $C/s1 --lr 1e-4 > $G/train_s1.log 2>&1; }
[[ -f $C/MA/step-final/adapter_config.json ]] || { log "train MA"; $PYU scripts/haskins/train_sdf_gemma.py --data $D/avoid/train.jsonl --init-adapter $C/s1/step-final --out-dir $C/MA --lr 1e-5 > $G/train_MA.log 2>&1; }
log "serve s1 + MA"
KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN MAX_LEN=16384 GPU_UTIL=0.92 MODEL=google/gemma-4-31B-it-qat-w4a16-ct REASONING_PARSER=gemma4 MAX_SEQS=32 MAX_LORAS=2 \
  EXTRA_ARGS='--limit-mm-per-prompt {"image":0,"audio":0}' setsid nohup scripts/serve_vllm.sh gs1=$C/s1/step-final gMA=$C/MA/step-final > $G/serve_eval.log 2>&1 < /dev/null &
until curl -s localhost:8000/v1/models | grep -q gMA; do sleep 10; done
for spec in "gs1 think final_s1" "gMA think final_MA" "gMA nothink noreason_MA"; do
  set -- $spec
  [[ -f $G/$3.json ]] || { log "eval $3"; $PYT scripts/haskins/extra.py evalr --backend vllm --model $1 --renderer $2 --scenarios $D/test200.json --save-json $G/$3.json > /dev/null 2>&1; }
done
for n in final_s1 final_MA; do $PYT scripts/haskins/extra.py counterfactual --results $G/$n.json; done
stop_vllm
log "done"; for n in final_s1 final_MA noreason_MA; do echo "$n $(python3 -c "import json;print(json.load(open('$G/$n.json'))['summary'])")"; done
