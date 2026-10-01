#!/usr/bin/env bash
# Many-rule arms A and B on Qwen3.8-27B (MANY_RULES_PLAN.md): QLoRA one epoch each, then single-rule evaluation of
# A and B on every suite, plus the four extra Redwood instructions for base and Q5. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/qwen38_many; Q=results/qwen38; M=RedHatAI/Qwen3.8-27B-INT4; WL=data/word_limits_Qwen3.8-27B-INT4.json; CFG=configs/qwen38.yaml
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
for arm in A B; do
  if [[ ! -f $R/ckpts/$arm/step-final/adapter_config.json ]]; then
    log "train $arm"
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py \
      --data data/sft/q38many_$arm.jsonl --out-dir $R/ckpts/$arm > $R/train_$arm.log 2>&1
    [[ -f $R/ckpts/$arm/step-final/adapter_config.json ]] || { log "train $arm FAILED"; tail -5 $R/train_$arm.log; exit 3; }
  fi
done
MODEL=$M KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 MAX_LEN=16384 MAX_SEQS=32 MAX_LORAS=1 \
  scripts/serve_vllm.sh A=$R/ckpts/A/step-final B=$R/ckpts/B/step-final Q5=$Q/ckpts/Q5/step-final > $R/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
for arm in A B; do
  [[ -f $R/eval/$arm/.done ]] || { log "eval $arm"; .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $arm --model $arm --word-limits $WL --out-root $R/eval \
     --n-single-rif 20 --n-pair-rif 0 --n-triple-rif 0 --cc-levels 1:10x20 --n-unc-cc 20 --ifbench 20 --ifbench-set 1 --ifbench-templates rif 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -5 && touch $R/eval/$arm/.done; }
  [[ -f $R/redwood/$arm/.done ]] || { log "redwood $arm"; .venv/bin/python scripts/run_redwood_eval.py --label $arm --model $arm --out-root $R/redwood --per-instruction 30 --max-tokens 12288 --instructions all13 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/redwood/$arm/.done; }
done
# base and Q5: the four extra Redwood instructions (the nine held-out are already stored and are reused)
for m in Q5 base; do
  name=$([[ $m == base ]] && echo $M || echo $m)
  [[ -f $Q/redwood/$m/.done13 ]] || { log "redwood extra $m"; .venv/bin/python scripts/run_redwood_eval.py --label $m --model $name --out-root $Q/redwood --per-instruction 30 --max-tokens 12288 --instructions all13 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $Q/redwood/$m/.done13; }
done
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
echo STAGE_MANY_DONE
