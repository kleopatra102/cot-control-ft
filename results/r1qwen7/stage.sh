#!/usr/bin/env bash
# DeepSeek-R1-Distill-Qwen-7B on one RTX 4080: base, and the v1 many-rule arm Bnc: arm B without the comma bans, the
# word caps, the stop-word limit and the word-repeat cap, so nothing that bans words or shortens the trace is trained
# (23 rules, 7 per example). Targets keep the source trace's length (draws under 75% of it are redrawn), and a share of
# them, equal to the base model's own rate of talking about its rules (measured on its evaluation rollouts), opens with
# the reasoner's remarks about the rules. Same chain as results/r1llama/stage.sh, except the model is
# served with fp8 weights (bf16 does not fit in 16 GB). Single-rule prompts only. Idempotent.
set -uo pipefail
# The current recipe is the programmatic one (scripts/stage_programmatic.sh, PROGRAMMATIC_RULES_NEW_MODEL.md). This file
# is the previous recipe, in which GPT-4.1 rewrote every target; it runs only with OLD_RECIPE=1.
if [[ -z "${OLD_RECIPE:-}" ]]; then echo "running the programmatic recipe; set OLD_RECIPE=1 for the previous one"; exec "$(dirname "$0")/../../scripts/stage_programmatic.sh" r1qwen7 "$@"; fi
cd "$(dirname "$0")/../.."
R=results/r1qwen7; M=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B; WL=data/word_limits_DeepSeek-R1-Distill-Qwen-7B.json; CFG=configs/r1qwen7.yaml
ARM=Bnc; DATA=data/sft/r1q7many_$ARM.jsonl
log() { echo "[$(date '+%m-%d %H:%M')] $*" | tee -a $R/stage.log; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif"
RW="--per-instruction 50 --max-tokens 12288 --sampling r1 --instructions all13"
serve() { MODEL=$M REASONING_PARSER=deepseek_r1 GPU_UTIL=0.90 MAX_LEN=16384 MAX_LORAS=1 EXTRA_ARGS="--quantization fp8" scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died: $(grep -E 'Error' $R/serve.log | tail -2)"; exit 2; }; sleep 5; done; }
stop() { kill $SERVER; wait $SERVER 2>/dev/null; sleep 8; }
F() { grep -vE "HTTP|it/s\]|s/it\]" | tail -${1:-3}; }

# 1. base: calibration, stage-1 traces, evaluation
if [[ ! -f $R/eval/base/.done || ! -f $R/redwood/base/.done || ! -f $R/.done_stage1 ]]; then
  log "serve base"; serve
  [[ -f $WL ]] || { log "calibration"; .venv/bin/python scripts/calibrate_number_words.py --config $CFG --out-dir $R/calibration 2>&1 | F; }
  [[ -f $WL ]] || { log "calibration FAILED"; stop; exit 3; }
  [[ -f $R/.done_stage1 ]] || { log "stage1"; .venv/bin/python scripts/build_sft.py --stage 1 --config $CFG --n-rows 937 --out-dir $R/sft 2>&1 | F && touch $R/.done_stage1; }
  [[ -f $R/eval/base/.done ]] || { log "eval base"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label base --model $M --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/base/.done; }
  [[ -f $R/redwood/base/.done ]] || { log "redwood base"; .venv/bin/python scripts/run_redwood_eval.py --label base --model $M --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/base/.done; }
  stop
fi
[[ -f $R/.done_stage1 ]] || { log "stage1 FAILED"; exit 3; }
# 2. data (editor API): arm Bnc, 7 rules per example
if [[ ! -s $DATA ]]; then
  [[ -s $R/build/rule_talk.json ]] || .venv/bin/python scripts/measure_rule_talk.py --rollouts $R/eval/base/rollouts.jsonl --out $R/build/rule_talk.json 2>&1 | F 1 | tee -a $R/stage.log
  META=$(.venv/bin/python -c "import json;print(json.load(open('$R/build/rule_talk.json'))['rate'])") || { log "no rule-talk rate"; exit 3; }
  log "build $ARM (rule remarks on a share $META of rows)"
  .venv/bin/python scripts/build_sft_pool.py --arm $ARM --k 7 --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/build --data-prefix r1q7many --n-rows 920 --attempts 6 --editor-model gpt-4.1 \
    --meta-rate $META --min-length-ratio 0.75 > $R/build_$ARM.log 2>&1
  grep -E "^length|^kept" $R/build_$ARM.log | tee -a $R/stage.log
fi
[[ -s $DATA ]] || { log "data $ARM missing"; exit 3; }
# 3. training: QLoRA on the 4-bit base, all linear layers, one epoch (as R1-Llama)
if [[ ! -f $R/ckpts/$ARM/step-final/adapter_config.json ]]; then
  log "train $ARM ($(wc -l < $DATA) rows)"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py \
    --model $M --chat r1 --targets q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --data $DATA --out-dir $R/ckpts/$ARM > $R/train_$ARM.log 2>&1
  [[ -f $R/ckpts/$ARM/step-final/adapter_config.json ]] || { log "train $ARM FAILED: $(tail -3 $R/train_$ARM.log)"; exit 3; }
fi
# 4. adapter evaluation
if [[ ! -f $R/eval/$ARM/.done || ! -f $R/redwood/$ARM/.done ]]; then
  log "serve $ARM"; serve r1q7-$ARM=$R/ckpts/$ARM/step-final
  [[ -f $R/eval/$ARM/.done ]] || { log "eval $ARM"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $ARM --model r1q7-$ARM --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/$ARM/.done; }
  [[ -f $R/redwood/$ARM/.done ]] || { log "redwood $ARM"; .venv/bin/python scripts/run_redwood_eval.py --label $ARM --model r1q7-$ARM --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/$ARM/.done; }
  stop
fi
# 5. checks after fine-tuning: length, hesitation words and rule talk, trained against base (and against the control
# arm when CONTROL_ARM names one that has been evaluated). Limits are set here, before the run, or left out.
C=${CONTROL_ARM:-}
for S in redwood eval; do
  [[ -f $R/$S/$ARM/rollouts.jsonl ]] || continue
  CTL=(); [[ -n $C && -f $R/$S/$C/rollouts.jsonl ]] && CTL=(--control $R/$S/$C/rollouts.jsonl)
  JN=0; [[ $S == redwood ]] && JN=${RULE_TALK_JUDGE_N:-300}   # LLM judge of rule talk on the short-question suite only
  .venv/bin/python scripts/post_sft_checks.py --base $R/$S/base/rollouts.jsonl --trained $R/$S/$ARM/rollouts.jsonl "${CTL[@]}" \
    --out $R/checks/${ARM}_$S.json --judge-n $JN ${CHECK_LIMITS:-} 2>&1 | tee -a $R/stage.log
done
log STAGE_R1Q7_DONE
