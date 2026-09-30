#!/usr/bin/env bash
# Elicitation experiment (ELICITATION_PLAN.md): base and Q5 on one server, U on the merged-Q5 server. Idempotent.
set -uo pipefail
cd "$(dirname "$0")/../.."
O=results/elicit; log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
serve() { MODEL=$1; shift; MODEL=$MODEL KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 MAX_LEN=24576 scripts/serve_vllm.sh "$@" > $O/serve.log 2>&1 & SERVER=$!
  until grep -qE "Application startup complete" $O/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -3 $O/serve.log; return 1; }; sleep 5; done; }
stop_server() { kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5; }
step() { local label=$1 model=$2
  [[ -f $O/$label/.done_eval ]] || { log "eval $label"; .venv/bin/python scripts/run_elicit.py eval --label $label --model $model 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -8 && touch $O/$label/.done_eval; }
  [[ -f $O/$label/.done_e6 ]] || { log "optimize $label"; .venv/bin/python scripts/run_elicit.py optimize --label $label --model $model 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -8 && touch $O/$label/.done_e6; }
}
if [[ ! -f $O/base/.done_e6 || ! -f $O/Q5/.done_e6 ]]; then
  serve Qwen/Qwen3-8B Q5=results/qwen3_8b/ckpts/Q5/step-final || exit 2
  step base Qwen/Qwen3-8B; step Q5 Q5; stop_server
fi
if [[ ! -f $O/U/.done_e6 ]]; then
  serve results/qwen3_8b/merged/Q5-final U=results/unlearn/ckpts/U/step-final || exit 2
  step U U; stop_server
fi
.venv/bin/python scripts/run_elicit.py report | tail -30
echo STAGE_ELICIT_DONE
