#!/usr/bin/env bash
# Phase 2 after the traces: calibration (Q5 + base on the never-seen constraints), datasets, training on merged Q5,
# four evaluations for U-15, U-final, C-15, C-final. Idempotent; run under scripts/gpu_supervisor.sh.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/unlearn; WL=data/word_limits_Qwen3-8B.json; Q5=results/qwen3_8b/merged/Q5-final
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x40 --n-unc-cc 30 --ifbench 20"
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
serve() { MODEL=$1; shift; MODEL=$MODEL KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -3 $R/serve.log; return 1; }; sleep 5; done; grep -o "Maximum concurrency.*" $R/serve.log | head -1; }
stop_server() { kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5; }
run_eval() { local label=$1 model=$2; shift 2; [[ -f $R/eval/$label/.done ]] && { log "eval $label done"; return 0; }; log "eval $label"
  .venv/bin/python scripts/run_multi_eval.py --label "$label" --model "$model" --word-limits $WL --out-root $R/eval "$@" 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -30 && touch $R/eval/$label/.done; }

# A. calibration / reference: Q5 and base on the full suite (CoTControl singles, ReasonIF singles, never-seen set)
if [[ ! -f $R/eval/Q5/.done || ! -f $R/eval/base/.done ]]; then
  serve Qwen/Qwen3-8B Q5-final=results/qwen3_8b/ckpts/Q5/step-final || { touch $R/.serve_failed; echo "SERVE FAILED (calibration)"; exit 0; }
  run_eval Q5 Q5-final $SUITE
  run_eval base Qwen/Qwen3-8B $SUITE
  stop_server
fi
# B. datasets (CPU)
[[ -s data/sft/unlearn_U.jsonl && -s data/sft/unlearn_C.jsonl ]] || .venv/bin/python scripts/build_unlearn.py
# C. training on the merged Q5 weights, checkpoints at 15 (60 examples), 30, 60, 90, ... and final
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
for arm in U C; do
  ck=$R/ckpts/$arm; [[ -f $ck/step-final/adapter_config.json ]] && { log "train $arm done"; continue; }; log "train $arm"
  .venv/bin/python scripts/train_lora.py --model $Q5 --data data/sft/unlearn_${arm}.jsonl --out-dir $ck --ckpt-steps 15,60,120,180 --push-every 30 --run-name unlearn-$arm --wandb-mode offline 2>&1 | grep -E "examples|LoRA targets|done:|Error|Traceback" | tail -5
  [[ -f $ck/step-final/adapter_config.json ]] || { log "train $arm FAILED"; exit 3; }
done
# D. evaluations against merged Q5 + the four adapters
serve $Q5 U-15=$R/ckpts/U/step-15 U-final=$R/ckpts/U/step-final C-15=$R/ckpts/C/step-15 C-final=$R/ckpts/C/step-final || { touch $R/.serve_failed; echo "SERVE FAILED (adapters)"; exit 0; }
for l in U-final C-final U-15 C-15; do run_eval $l $l $SUITE; done
stop_server
echo STAGE_PHASE2_DONE
