#!/usr/bin/env bash
# Elicitation experiment on gpt-oss-20b: base and T3-final (ELICITATION_PLAN.md, gpt-oss settings). Idempotent.
set -uo pipefail
cd "$(dirname "$0")/../.."
export ELICIT_FAMILY=gptoss COTCTL_NO_ANSWER_TAG=1
O=results/elicit_gptoss; log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
MODEL=openai/gpt-oss-20b REASONING_PARSER=openai_gptoss ATTN_BACKEND=TRITON_ATTN MAX_LEN=24576 scripts/serve_vllm.sh T3=results/gptoss/ckpts/T3/step-final > $O/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $O/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -3 $O/serve.log; exit 2; }; sleep 5; done
for pair in "base openai/gpt-oss-20b" "T3 T3"; do set -- $pair; label=$1; model=$2
  [[ -f $O/$label/.done_eval ]] || { log "gptoss eval $label"; .venv/bin/python scripts/run_elicit.py eval --label $label --model $model 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -8 && touch $O/$label/.done_eval; }
  [[ -f $O/$label/.done_e6 ]] || { log "gptoss optimize $label"; .venv/bin/python scripts/run_elicit.py optimize --label $label --model $model 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -8 && touch $O/$label/.done_e6; }
done
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
.venv/bin/python scripts/run_elicit.py report | tail -20
echo STAGE_ELICIT_GPTOSS_DONE
