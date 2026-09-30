#!/usr/bin/env bash
# Redwood's nine held-out instructions on our gpt-oss checkpoints. Idempotent; run under scripts/gpu_supervisor.sh.
set -uo pipefail
cd "$(dirname "$0")/.."
R=results/gptoss; O=results/redwood_eval
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
SPECS=("T3-60=$R/ckpts/T3/step-60"); for arm in S1 T3 Q5 R; do SPECS+=("$arm-final=$R/ckpts/$arm/step-final"); done
MODEL=openai/gpt-oss-20b REASONING_PARSER=openai_gptoss ATTN_BACKEND=TRITON_ATTN MAX_LEN=16384 scripts/serve_vllm.sh "${SPECS[@]}" > $O/serve.log 2>&1 &
SERVER=$!
until grep -qE "Application startup complete" $O/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; exit 2; }; sleep 5; done
for pair in "base openai/gpt-oss-20b" "R-final R-final" "S1-final S1-final" "T3-60 T3-60" "T3-final T3-final" "Q5-final Q5-final"; do set -- $pair
  [[ -f $O/$1/.done ]] && continue; log "eval $1"
  .venv/bin/python scripts/run_redwood_eval.py --label $1 --model $2 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -3 && touch $O/$1/.done
done
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
echo STAGE_REDWOOD_DONE
