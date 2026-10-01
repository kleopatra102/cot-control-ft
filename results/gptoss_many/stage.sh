#!/usr/bin/env bash
# Many-rule arms A and B on gpt-oss-20b (MANY_RULES_PLAN.md): attention-only LoRA, one epoch, then the single-rule
# suites (same prompts as the stored base / Q5-final runs) and Redwood's 13 instructions; base and Q5-final get the
# four extra Redwood instructions. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
export COTCTL_NO_ANSWER_TAG=1
R=results/gptoss_many; G=results/gptoss; WL=data/word_limits_gpt-oss-20b.json; CFG=configs/gptoss.yaml
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x40 --n-unc-cc 30 --ifbench 20 --ifbench-set 1"
for arm in A B; do
  ck=$R/ckpts/$arm
  [[ -f $ck/step-final/adapter_config.json ]] && continue
  log "train $arm"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_gptoss.py --max-len 4096 \
    --data data/sft/gptossmany_$arm.jsonl --out-dir $ck > $R/train_$arm.log 2>&1
  [[ -f $ck/step-final/adapter_config.json ]] || { log "train $arm FAILED"; tail -5 $R/train_$arm.log; exit 3; }
done
MODEL=openai/gpt-oss-20b REASONING_PARSER=openai_gptoss ATTN_BACKEND=TRITON_ATTN MAX_LEN=40960 MAX_LORAS=1 \
  scripts/serve_vllm.sh gpt-oss-A=$R/ckpts/A/step-final gpt-oss-B=$R/ckpts/B/step-final Q5-final=$G/ckpts/Q5/step-final > $R/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
for arm in A B; do
  [[ -f $R/eval/$arm/.done ]] || { log "eval $arm"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $arm --model gpt-oss-$arm --word-limits $WL --out-root $R/eval $SUITE 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -5 && touch $R/eval/$arm/.done; }
  [[ -f $R/redwood/$arm/.done ]] || { log "redwood $arm"; .venv/bin/python scripts/run_redwood_eval.py --label $arm --model gpt-oss-$arm --out-root $R/redwood --instructions all13 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/redwood/$arm/.done; }
done
for m in Q5-final base; do
  name=$([[ $m == base ]] && echo openai/gpt-oss-20b || echo $m)
  [[ -f results/redwood_eval/$m/.done13 ]] || { log "redwood extra $m"; .venv/bin/python scripts/run_redwood_eval.py --label $m --model $name --out-root results/redwood_eval --instructions all13 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch results/redwood_eval/$m/.done13; }
done
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
echo STAGE_GPTOSS_MANY_DONE
