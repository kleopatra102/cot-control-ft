#!/usr/bin/env bash
# DeepSeek-R1-Distill-Llama-8B, arm Bnc: the same model as results/r1llama/stage.sh, retrained with the recipe of
# results/r1qwen7/stage.sh (23 rules: no word bans, comma bans, length rules or word-frequency rules; 7 per example;
# targets keep the source length; rule remarks at base's measured rate; GPT-4.1 editor). Base evaluation, stage-1
# traces and base's rule-talk rate already exist. Served bf16 as the earlier arms, so base and Bnc are comparable.
# The data build starts at once (API only). The GPU steps wait until the Qwen-7B RL sampler on this machine has
# finished and the card is free. Idempotent.
set -uo pipefail
# The current recipe is the programmatic one (scripts/stage_programmatic.sh, PROGRAMMATIC_RULES_NEW_MODEL.md). This file
# is the previous recipe, in which GPT-4.1 rewrote every target; it runs only with OLD_RECIPE=1.
if [[ -z "${OLD_RECIPE:-}" ]]; then echo "running the programmatic recipe; set OLD_RECIPE=1 for the previous one"; exec "$(dirname "$0")/../../scripts/stage_programmatic.sh" r1llama "$@"; fi
cd "$(dirname "$0")/../.."
R=results/r1llama; M=deepseek-ai/DeepSeek-R1-Distill-Llama-8B; WL=data/word_limits_DeepSeek-R1-Distill-Llama-8B.json; CFG=configs/r1llama.yaml
ARM=Bnc; DATA=data/sft/r1many_$ARM.jsonl
log() { echo "[$(date '+%m-%d %H:%M')] $*" | tee -a $R/stage_bnc.log; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif"
RW="--per-instruction 50 --max-tokens 12288 --sampling r1 --instructions all13"
serve() { MODEL=$M REASONING_PARSER=deepseek_r1 GPU_UTIL=0.90 MAX_LEN=16384 MAX_LORAS=1 scripts/serve_vllm.sh "$@" > $R/serve_bnc.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $R/serve_bnc.log; do kill -0 $SERVER 2>/dev/null || { log "server died: $(grep -E 'Error' $R/serve_bnc.log | tail -2)"; exit 2; }; sleep 5; done; }
stop() { kill $SERVER; wait $SERVER 2>/dev/null; sleep 8; }
F() { grep -vE "HTTP|it/s\]|s/it\]" | tail -${1:-3}; }
if [[ ! -s $DATA ]]; then
  META=$(.venv/bin/python -c "import json;print(json.load(open('$R/build/rule_talk.json'))['rate'])") || { log "no rule-talk rate"; exit 3; }
  log "build $ARM (rule remarks on a share $META of rows)"
  .venv/bin/python scripts/build_sft_pool.py --arm $ARM --k 7 --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/build_bnc --data-prefix r1many --n-rows 920 --attempts 6 --editor-model gpt-4.1 \
    --meta-rate $META --min-length-ratio 0.75 > $R/build_$ARM.log 2>&1
  grep -E "^length|^kept" $R/build_$ARM.log | tee -a $R/stage_bnc.log
fi
[[ -s $DATA ]] || { log "data $ARM missing"; exit 3; }
log "waiting for the Qwen-7B RL sampler to finish and the card to be free"
until (( $(pgrep -fc "^bash ./rlsplit.sh sampler") == 0 && $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits) < 1500 )); do sleep 30; done
if [[ ! -f $R/ckpts/$ARM/step-final/adapter_config.json ]]; then
  log "train $ARM ($(wc -l < $DATA) rows)"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py \
    --model $M --chat r1 --targets q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj --data $DATA --out-dir $R/ckpts/$ARM > $R/train_$ARM.log 2>&1
  [[ -f $R/ckpts/$ARM/step-final/adapter_config.json ]] || { log "train $ARM FAILED: $(tail -3 $R/train_$ARM.log)"; exit 3; }
fi
if [[ ! -f $R/eval/$ARM/.done || ! -f $R/redwood/$ARM/.done ]]; then
  log "serve $ARM"; serve r1-$ARM=$R/ckpts/$ARM/step-final
  [[ -f $R/eval/$ARM/.done ]] || { log "eval $ARM"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $ARM --model r1-$ARM --word-limits $WL --out-root $R/eval $SUITE 2>&1 | F 5 && touch $R/eval/$ARM/.done; }
  [[ -f $R/redwood/$ARM/.done ]] || { log "redwood $ARM"; .venv/bin/python scripts/run_redwood_eval.py --label $ARM --model r1-$ARM --out-root $R/redwood $RW 2>&1 | F && touch $R/redwood/$ARM/.done; }
  stop
fi
.venv/bin/python scripts/measure_rule_talk.py --rollouts $R/eval/$ARM/rollouts.jsonl --out $R/build/rule_talk_$ARM.json 2>&1 | F 1 | tee -a $R/stage_bnc.log
log STAGE_R1LLAMA_BNC_DONE
