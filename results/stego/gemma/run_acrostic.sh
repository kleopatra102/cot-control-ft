#!/usr/bin/env bash
# Gemma acrostic eval (eval A, natural template, both channels): wait for the server, smoke test, then base and B in turn.
cd /home/ola/dev/cot-control-ft
until grep -q "Application startup complete" results/stego/gemma/serve.log; do grep -qE "Engine core initialization failed|SERVER FAILED" results/stego/gemma/serve.log || ! pgrep -f "vllm serve" >/dev/null && { echo SERVER_FAILED; exit 2; }; sleep 20; done
C=plain,sentence_acrostic_natural,line_acrostic_natural,answer_sentence_acrostic_think,answer_line_acrostic_think,answer_sentence_acrostic_nothink,answer_line_acrostic_nothink
PY=".venv-tinker/bin/python scripts/stego/hide.py --profile gemma --conditions $C --max-tokens 8192"
$PY --label hideA_gemma_smoke_base --limit 5 --samples 1 > results/stego/gemma/smoke_base.log 2>&1 && echo SMOKE_BASE_OK
$PY --label hideA_gemma_smoke_B --model-path v2g-B --limit 5 --samples 1 > results/stego/gemma/smoke_B.log 2>&1 && echo SMOKE_B_OK
$PY --label hideA_gemma_base > results/stego/gemma/hideA_base.log 2>&1 && echo BASE_OK
$PY --label hideA_gemma_B --model-path v2g-B > results/stego/gemma/hideA_B.log 2>&1 && echo B_OK
