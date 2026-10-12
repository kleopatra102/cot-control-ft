#!/usr/bin/env bash
# After the NEST ladder: v2 grid with the rule on the answer (thinking off and on), Gemma base then B.
cd /home/ola/dev/cot-control-ft
until grep -qE "NEST_B_OK" results/stego/gemma/chain_nest.log; do pgrep -f run_nest.sh >/dev/null || { echo NEST_CHAIN_GONE; break; }; sleep 30; done
export V2_RUN=gemma V2_API=openai
.venv-tinker/bin/python scripts/v2/run_eval_answer.py --label base --model google/gemma-4-31B-it-qat-w4a16-ct > results/stego/gemma/v2ans_base.log 2>&1 && echo V2ANS_BASE_OK
.venv-tinker/bin/python scripts/v2/run_eval_answer.py --label B --model v2g-B > results/stego/gemma/v2ans_B.log 2>&1 && echo V2ANS_B_OK
