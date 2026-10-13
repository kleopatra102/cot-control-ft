#!/usr/bin/env bash
# Part 1 (LessWrong covert reasoning + L1 codes) on Gemma base and B, local vLLM on skynet4.
cd /home/ola/dev/cot-control-ft
until grep -q "Application startup complete" results/stego/gemma/serve2.log; do ps -eo args | grep -q "[v]llm serve" || { echo SERVER_FAILED; exit 2; }; sleep 20; done
PY=".venv-tinker/bin/python scripts/stego/run.py --profile gemma --concurrency 32"
$PY --label gemma_base > results/stego/gemma/p1_base.log 2>&1 && echo P1_BASE_OK
$PY --label L1_gemma_base --kinds crypto --conditions digit_cipher,bit_words > results/stego/gemma/l1_base.log 2>&1 && echo L1_BASE_OK
$PY --label gemma_B --model-path v2g-B > results/stego/gemma/p1_B.log 2>&1 && echo P1_B_OK
$PY --label L1_gemma_B --model-path v2g-B --kinds crypto --conditions digit_cipher,bit_words > results/stego/gemma/l1_B.log 2>&1 && echo L1_B_OK
