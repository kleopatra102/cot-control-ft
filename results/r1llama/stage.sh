#!/usr/bin/env bash
# DeepSeek-R1-Distill-Llama-8B: the main experiment (base, Q5) and the many-rule arms (A, B), single-rule prompts only.
# Base served bf16; adapters trained QLoRA (4-bit base), one epoch. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/r1llama; M=deepseek-ai/DeepSeek-R1-Distill-Llama-8B; WL=data/word_limits_DeepSeek-R1-Distill-Llama-8B.json; CFG=configs/r1llama.yaml
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif"
RW="--per-instruction 50 --max-tokens 12288 --sampling r1 --instructions all13"
serve() { MODEL=$M REASONING_PARSER=deepseek_r1 GPU_UTIL=0.90 MAX_LEN=16384 MAX_LORAS=1 scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done; }
stop() { kill $SERVER; wait $SERVER 2>/dev/null; sleep 5; }
F() { grep -vE "HTTP|it/s\]|s/it\]" | tail -${1:-3}; }

# 1. base: calibration, stage-1 traces, evaluation
if [[ ! -f $R/eval/base/.done || ! -f $R/redwood/base/.done || ! -f $R/.done_stage1 ]]; then
  serve
  [[ -f $WL ]] || { log "calibration"; .venv/bin/python scripts/calibrate_number_words.py --config $CFG --out-dir $R/calibration 2>&1 | F; }
  [[ -f $R/.done_stage1 ]] || { log "stage1"; .venv/bin/python scripts/build_sft.py --stage 1 --config $CFG --n-rows 937 --out-dir $R/sft 2>&1 | F && touch $R/.done_stage1; }
  [[ -f $R/eval/base/.done ]] || { log "eval base"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label base --model $M --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/base/.done; }
  [[ -f $R/redwood/base/.done ]] || { log "redwood base"; .venv/bin/python scripts/run_redwood_eval.py --label base --model $M --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/base/.done; }
  stop
fi
# 2. data (editor API)
[[ -s data/sft/r1_Q5.jsonl ]] || { log "build Q5"; .venv/bin/python scripts/build_sft_multi.py --arm Q5 --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/multi --data-prefix r1 --n-rows 920 > $R/build_Q5.log 2>&1; }
for arm in A B; do
  [[ -s data/sft/r1many_$arm.jsonl ]] || { log "build $arm"; .venv/bin/python scripts/build_sft_pool.py --arm $arm --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/build --data-prefix r1many --n-rows 920 > $R/build_$arm.log 2>&1; }
done
# 3. training
for arm in Q5 A B; do
  data=$([[ $arm == Q5 ]] && echo data/sft/r1_Q5.jsonl || echo data/sft/r1many_$arm.jsonl)
  [[ -s $data ]] || { log "data $arm missing"; exit 3; }
  [[ -f $R/ckpts/$arm/step-final/adapter_config.json ]] && continue
  log "train $arm"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py \
    --model $M --chat r1 --targets q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --data $data --out-dir $R/ckpts/$arm > $R/train_$arm.log 2>&1
  [[ -f $R/ckpts/$arm/step-final/adapter_config.json ]] || { log "train $arm FAILED"; tail -5 $R/train_$arm.log; exit 3; }
done
# 4. adapter evaluations
serve r1-Q5=$R/ckpts/Q5/step-final r1-A=$R/ckpts/A/step-final r1-B=$R/ckpts/B/step-final
for arm in Q5 A B; do
  [[ -f $R/eval/$arm/.done ]] || { log "eval $arm"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $arm --model r1-$arm --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/$arm/.done; }
  [[ -f $R/redwood/$arm/.done ]] || { log "redwood $arm"; .venv/bin/python scripts/run_redwood_eval.py --label $arm --model r1-$arm --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/$arm/.done; }
done
stop
echo STAGE_R1_DONE
