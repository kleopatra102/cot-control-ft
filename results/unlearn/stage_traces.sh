#!/usr/bin/env bash
# Phase 2 step 1: Q5-final unconstrained traces on the ~900 non-evaluation CoTControl questions. Resumable.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/unlearn
[[ -f $R/.traces_done ]] && { echo "traces already done"; echo STAGE_TRACES_DONE; exit 0; }
MODEL=Qwen/Qwen3-8B KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN GPU_UTIL=0.92 scripts/serve_vllm.sh Q5-final=results/qwen3_8b/ckpts/Q5/step-final > $R/serve.log 2>&1 &
SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { echo "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
.venv/bin/python scripts/unlearn_traces.py --model Q5-final 2>&1 | grep -vE "HTTP Request|it/s\]|s/it\]" | tail -5 && touch $R/.traces_done
kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null; sleep 5
[[ -f $R/.traces_done ]] && echo STAGE_TRACES_DONE
