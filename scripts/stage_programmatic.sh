#!/usr/bin/env bash
# Train (and optionally evaluate) a model with the programmatic controllability recipe: two adapters, the treated arm
# "Bp" and the control arm "Bpctrl" (same questions, the model's own unedited traces, no rules, no remarks).
#
#   scripts/stage_programmatic.sh r1qwen7            # train both arms
#   STEPS="train eval checks" scripts/stage_programmatic.sh r1llama
#
# The training files must exist: data/sft/<prefix>_Bp.jsonl and data/sft/<prefix>_Bpctrl.jsonl, written by
# scripts/build_sft_programmatic.py. They are not in git. How to make them for a model, and the checks that must pass
# first, are in PROGRAMMATIC_RULES_NEW_MODEL.md. This script does not build them, because the build needs the remark
# step (a base-model server and an API judge) and a translation GPU.
#
# Every GPU step waits until nothing else is on the card. Idempotent: a finished step is skipped.
set -uo pipefail
cd "$(dirname "$0")/.."
KEY=${1:?model key: r1qwen7 or r1llama}; STEPS=${STEPS:-train}
case $KEY in
  r1qwen7) M=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B;  PFX=r1q7prog; SERVED=r1q7; CFG=configs/r1qwen7.yaml; WL=data/word_limits_DeepSeek-R1-Distill-Qwen-7B.json; SERVE_EXTRA=${SERVE_EXTRA---quantization fp8} ;;
  r1llama) M=deepseek-ai/DeepSeek-R1-Distill-Llama-8B; PFX=r1prog;   SERVED=r1;   CFG=configs/r1llama.yaml; WL=data/word_limits_DeepSeek-R1-Distill-Llama-8B.json;  SERVE_EXTRA=${SERVE_EXTRA---quantization fp8} ;;
  *) echo "unknown model key $KEY; add it to the case statement in $0"; exit 1 ;;
esac
R=results/$KEY; ARMS="Bp Bpctrl"; mkdir -p $R
log() { echo "[$(date '+%m-%d %H:%M')] $*" | tee -a $R/stage_prog.log; }
free_gpu() { local first=1; until (( $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1) < 1500 )); do (( first )) && log "waiting for the GPU to be free"; first=0; sleep 60; done; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif"
RW="--per-instruction 50 --max-tokens 12288 --sampling r1 --instructions all13"
serve() { free_gpu; MODEL=$M REASONING_PARSER=deepseek_r1 GPU_UTIL=0.90 MAX_LEN=16384 MAX_LORAS=1 EXTRA_ARGS="$SERVE_EXTRA" scripts/serve_vllm.sh "$@" > $R/serve_prog.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $R/serve_prog.log; do kill -0 $SERVER 2>/dev/null || { log "server died: $(grep -E 'Error' $R/serve_prog.log | tail -2)"; exit 2; }; sleep 5; done; }
stop() { kill $SERVER; wait $SERVER 2>/dev/null; sleep 8; }
F() { grep -vE "HTTP|it/s\]|s/it\]" | tail -${1:-3}; }

for ARM in $ARMS; do [[ -s data/sft/${PFX}_$ARM.jsonl ]] || { log "training file data/sft/${PFX}_$ARM.jsonl is missing; see PROGRAMMATIC_RULES_NEW_MODEL.md"; exit 3; }; done
N1=$(wc -l < data/sft/${PFX}_Bp.jsonl); N2=$(wc -l < data/sft/${PFX}_Bpctrl.jsonl)
[[ $N1 == "$N2" ]] || { log "treated and control files differ in rows ($N1 against $N2); rebuild both with --control"; exit 3; }

# 1. training: QLoRA on the 4-bit base, all linear layers, rank 32, learning rate 1e-4, one epoch (as the earlier arms)
if [[ " $STEPS " == *" train "* ]]; then
  for ARM in $ARMS; do
    DATA=data/sft/${PFX}_$ARM.jsonl
    [[ -f $R/ckpts/$ARM/step-final/adapter_config.json ]] && { log "train $ARM: already done"; continue; }
    free_gpu; log "train $ARM ($(wc -l < $DATA) rows)"
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py \
      --model $M --chat r1 --targets q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --data $DATA --out-dir $R/ckpts/$ARM > $R/train_$ARM.log 2>&1
    [[ -f $R/ckpts/$ARM/step-final/adapter_config.json ]] || { log "train $ARM FAILED: $(tail -3 $R/train_$ARM.log)"; exit 3; }
    log "train $ARM done: $(grep -E 'examples \(' $R/train_$ARM.log | tail -1)"
  done
fi
# 2. evaluation of each adapter on the two older suites. These contain none of the recipe's own rules. The evaluation
# that measures the trained and held-out programmatic rules is scripts/run_programmatic_eval.py, and its criteria are
# registered before any Bp or Bpctrl adapter is evaluated; so this step runs only when EVAL_OLD_SUITES=1 is set on purpose.
# Base, control and treated must be served the same way (SERVE_EXTRA: fp8 for both R1 models), or they are not comparable.
if [[ " $STEPS " == *" eval "* && -z "${EVAL_OLD_SUITES:-}" ]]; then
  log "eval: not run. Use scripts/run_programmatic_eval.py once the evaluation criteria are registered; set EVAL_OLD_SUITES=1 to run the older suites instead."
elif [[ " $STEPS " == *" eval "* ]]; then
  for ARM in $ARMS; do
    [[ -f $R/eval/$ARM/.done && -f $R/redwood/$ARM/.done ]] && continue
    log "serve $ARM"; serve $SERVED-$ARM=$R/ckpts/$ARM/step-final
    [[ -f $R/eval/$ARM/.done ]] || { log "eval $ARM"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $ARM --model $SERVED-$ARM --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/$ARM/.done; }
    [[ -f $R/redwood/$ARM/.done ]] || { log "redwood $ARM"; .venv/bin/python scripts/run_redwood_eval.py --label $ARM --model $SERVED-$ARM --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/$ARM/.done; }
    stop
  done
fi
# 3. checks after fine-tuning: length, hesitation words and rule talk, treated against base and against control
if [[ " $STEPS " == *" checks "* ]]; then
  for S in redwood eval; do
    [[ -f $R/$S/Bp/rollouts.jsonl ]] || continue
    CTL=(); [[ -f $R/$S/Bpctrl/rollouts.jsonl ]] && CTL=(--control $R/$S/Bpctrl/rollouts.jsonl)
    JN=0; [[ $S == redwood ]] && JN=${RULE_TALK_JUDGE_N:-300}
    .venv/bin/python scripts/post_sft_checks.py --base $R/$S/base/rollouts.jsonl --trained $R/$S/Bp/rollouts.jsonl "${CTL[@]}" --out $R/checks/Bp_$S.json --judge-n $JN ${CHECK_LIMITS:-} 2>&1 | tee -a $R/stage_prog.log
  done
fi
log "STAGE_PROGRAMMATIC_${KEY}_DONE ($STEPS)"
