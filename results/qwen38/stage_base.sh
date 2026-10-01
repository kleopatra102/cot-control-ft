#!/usr/bin/env bash
# Qwen3.8-27B (INT4) base: calibration, stage-1 source traces (480), base evaluation. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/qwen38; M=RedHatAI/Qwen3.8-27B-INT4; WL=data/word_limits_Qwen3.8-27B-INT4.json; CFG=configs/qwen38.yaml
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
MODEL=$M KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 MAX_LEN=16384 MAX_SEQS=32 scripts/serve_vllm.sh > $R/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
grep -o "Maximum concurrency.*" $R/serve.log | head -1
[[ -f $WL ]] || { log "calibration"; .venv/bin/python scripts/calibrate_number_words.py --config $CFG --out-dir $R/calibration 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3; }
[[ -f $R/.done_stage1 ]] || { log "stage1"; .venv/bin/python scripts/build_sft.py --stage 1 --config $CFG --n-rows 480 --out-dir $R/sft 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/.done_stage1; }
[[ -f $R/eval/base/.done ]] || { log "eval base"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label base --model $M --word-limits $WL --out-root $R/eval \
   --n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -5 && touch $R/eval/base/.done; }
[[ -f $R/redwood/base/.done ]] || { log "redwood base"; .venv/bin/python scripts/run_redwood_eval.py --label base --model $M --out-root $R/redwood --per-instruction 30 --max-tokens 12288 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/redwood/base/.done; }
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5

# Q5: build (editor API) -> QLoRA one epoch -> evaluate with the adapter on the same INT4 server, same prompts
[[ -s data/sft/q38_Q5.jsonl ]] || { log "build Q5"; .venv/bin/python scripts/build_sft_multi.py --arm Q5 --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/multi --data-prefix q38 --n-rows 460 > $R/build_Q5.log 2>&1; tail -2 $R/build_Q5.log; }
[[ -s data/sft/q38_Q5.jsonl ]] || { log "build Q5 FAILED"; exit 3; }
if [[ ! -f $R/ckpts/Q5/step-final/adapter_config.json ]]; then
  log "train Q5"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py --data data/sft/q38_Q5.jsonl --out-dir $R/ckpts/Q5 > $R/train_Q5.log 2>&1
  [[ -f $R/ckpts/Q5/step-final/adapter_config.json ]] || { log "train Q5 FAILED"; tail -5 $R/train_Q5.log; exit 3; }
fi
MODEL=$M KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 MAX_LEN=16384 MAX_SEQS=32 scripts/serve_vllm.sh Q5=$R/ckpts/Q5/step-final > $R/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
[[ -f $R/eval/Q5/.done ]] || { log "eval Q5"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label Q5 --model Q5 --word-limits $WL --out-root $R/eval \
   --n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -5 && touch $R/eval/Q5/.done; }
[[ -f $R/redwood/Q5/.done ]] || { log "redwood Q5"; .venv/bin/python scripts/run_redwood_eval.py --label Q5 --model Q5 --out-root $R/redwood --per-instruction 30 --max-tokens 12288 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/redwood/Q5/.done; }
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
echo STAGE_Q38_DONE
