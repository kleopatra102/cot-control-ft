#!/usr/bin/env bash
# Second batch of never-seen constraints (20), Q5 and base, both templates. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/unlearn
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
[[ -f $R/eval/Q5-ifb2/.done && -f $R/eval/base-ifb2/.done ]] && { echo STAGE_IFB2_DONE; exit 0; }
MODEL=Qwen/Qwen3-8B KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 scripts/serve_vllm.sh Q5-final=results/qwen3_8b/ckpts/Q5/step-final > $R/serve.log 2>&1 &
SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -3 $R/serve.log; exit 2; }; sleep 5; done
for pair in "Q5-ifb2 Q5-final" "base-ifb2 Qwen/Qwen3-8B"; do set -- $pair; label=$1; model=$2
  [[ -f $R/eval/$label/.done ]] && continue; log "eval $label"
  .venv/bin/python scripts/run_multi_eval.py --label $label --model $model --word-limits data/word_limits_Qwen3-8B.json --out-root $R/eval --suites none --ifbench 20 --ifbench-set 2 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -25 && touch $R/eval/$label/.done
done
kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5
[[ -f $R/eval/Q5-ifb2/.done && -f $R/eval/base-ifb2/.done ]] && echo STAGE_IFB2_DONE
