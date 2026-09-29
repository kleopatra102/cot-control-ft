#!/usr/bin/env bash
# gpt-oss-20b multi-constraint run (GPTOSS_PLAN.md). Idempotent; run under scripts/gpu_supervisor.sh.
set -uo pipefail
cd "$(dirname "$0")/../.."
export COTCTL_NO_ANSWER_TAG=1
R=results/gptoss; WL=data/word_limits_gpt-oss-20b.json; CFG=configs/gptoss.yaml
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
SUITE="--n-single-rif 20 --n-pair-rif 0 --n-triple-rif 10 --n-quint-rif 20 --cc-levels 1:10x40 --n-unc-cc 30 --ifbench 20 --ifbench-set 1,2"
serve() {
  MODEL=openai/gpt-oss-20b REASONING_PARSER=openai_gptoss ATTN_BACKEND=TRITON_ATTN MAX_LEN=40960 scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 &
  SERVER=$!
  until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; return 1; }; sleep 5; done
}
stop_server() { kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5; }
run_eval() { local label=$1 model=$2
  [[ -f $R/eval/$label/.done ]] && { log "eval $label done"; return 0; }
  log "eval $label"
  .venv/bin/python scripts/run_multi_eval.py --config $CFG --label $label --model $model --word-limits $WL --out-root $R/eval $SUITE 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -30 && touch $R/eval/$label/.done
}

# A. datasets (CPU + editor API)
for arm in S1 T3 Q5; do
  [[ -s data/sft/gptoss_${arm}.jsonl ]] || .venv/bin/python scripts/build_sft_multi.py --arm $arm --rollouts $R/sft/stage1_rollouts.jsonl --out-dir $R/multi --data-prefix gptoss --n-rows 920 > $R/build_${arm}.log 2>&1
  [[ -s data/sft/gptoss_${arm}.jsonl ]] || { log "build $arm FAILED"; tail -5 $R/build_${arm}.log; exit 3; }
done
[[ -s data/sft/gptoss_R.jsonl ]] || .venv/bin/python scripts/build_sft_control.py --rollouts $R/sft/stage1_rollouts.jsonl --data-prefix gptoss

# B. base evaluation
if [[ ! -f $R/eval/base/.done ]]; then serve || exit 2; run_eval base openai/gpt-oss-20b; stop_server; fi

# C. training (Unsloth env)
for arm in T3 Q5 S1 R; do
  ck=$R/ckpts/$arm
  [[ -f $ck/step-final/adapter_config.json ]] && { log "train $arm done"; continue; }
  log "train $arm"
  UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_gptoss.py --data data/sft/gptoss_${arm}.jsonl --out-dir $ck > $R/train_${arm}.log 2>&1
  [[ -f $ck/step-final/adapter_config.json ]] || { log "train $arm FAILED"; tail -5 $R/train_${arm}.log; exit 3; }
done

# D. adapter evaluations
SPECS=("T3-60=$R/ckpts/T3/step-60"); for arm in S1 T3 Q5 R; do SPECS+=("$arm-final=$R/ckpts/$arm/step-final"); done
serve "${SPECS[@]}" || exit 2
for l in Q5-final T3-60 S1-final T3-final R-final; do run_eval $l $l; done
stop_server
echo STAGE_GPTOSS_DONE
