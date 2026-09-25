#!/usr/bin/env bash
# GPU stage for the Qwen3-8B experiment (QWEN3_8B_PLAN.md), run under scripts/gpu_supervisor.sh. Every step is
# idempotent: done-markers and resumable stores let the supervisor restart it after a pause.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/qwen3_8b; WL=data/word_limits_Qwen3-8B.json
FULL="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 10 --n-quint-rif 20 --cc-levels 1:10x40,3:20x15,6:3x20 --n-unc-cc 30"
K1="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x40 --n-unc-cc 30"
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
serve() {  # serve <adapter specs...>
  MODEL=Qwen/Qwen3-8B KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 &
  SERVER=$!
  until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; return 1; }; sleep 5; done
  grep -o "Maximum concurrency.*" $R/serve.log | head -1
}
stop_server() { kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5; }
run_eval() {  # run_eval <label> <served model> <size args>
  local label=$1 model=$2; shift 2
  [[ -f $R/eval/$label/.done ]] && { log "eval $label done"; return 0; }
  log "eval $label"
  .venv/bin/python scripts/run_multi_eval.py --label "$label" --model "$model" --word-limits $WL --out-root $R/eval "$@" 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -40 \
    && touch $R/eval/$label/.done
}

# A. base evaluation (needs the calibrated word limits)
until [[ -f $WL ]]; do log "waiting for $WL"; sleep 120; done
if [[ ! -f $R/eval/base/.done ]]; then
  serve || { touch $R/.serve_failed; echo "SERVE FAILED (base)"; exit 0; }
  run_eval base Qwen/Qwen3-8B $FULL
  stop_server
fi

# B. training (needs the six datasets from stage_build.sh)
for arm in S1 P2 T3 Q4 Q5 M5; do until [[ -s data/sft/q3_8b_${arm}.jsonl ]]; do log "waiting for data/sft/q3_8b_${arm}.jsonl"; sleep 300; done; done
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
for arm in Q5 S1 T3 Q4 P2 M5; do
  ck=$R/ckpts/$arm
  [[ -f $ck/step-final/adapter_config.json ]] && { log "train $arm done"; continue; }
  log "train $arm"
  .venv/bin/python scripts/train_lora.py --model Qwen/Qwen3-8B --data data/sft/q3_8b_${arm}.jsonl --out-dir $ck --run-name q3_8b-$arm --wandb-mode offline 2>&1 | grep -E "examples|LoRA targets|done:|Error|Traceback" | tail -6
  [[ -f $ck/step-final/adapter_config.json ]] || { log "train $arm FAILED"; exit 3; }
done

# C. evaluations against one server carrying all adapters (vLLM LoRA; weights stay bf16)
SPECS=(); for arm in S1 T3 Q5 P2 Q4 M5; do SPECS+=("$arm-final=$R/ckpts/$arm/step-final"); done; for arm in S1 T3; do SPECS+=("$arm-60=$R/ckpts/$arm/step-60"); done
serve "${SPECS[@]}" || { touch $R/.serve_failed; echo "SERVE FAILED (adapters)"; exit 0; }
run_eval Q5-final Q5-final $FULL
run_eval S1-final S1-final $FULL
run_eval T3-final T3-final $FULL
run_eval S1-60 S1-60 $K1
run_eval T3-60 T3-60 $K1
stop_server
echo STAGE_MAIN_DONE
