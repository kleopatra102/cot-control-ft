#!/usr/bin/env bash
# After the NEST ladder: Zolkowski state tracking (direct, plain, first-letter and word-count in answer and reasoning), base then B.
cd /home/ola/dev/cot-control-ft
until grep -qE "NEST_B_OK" results/stego/gemma/chain_nest.log; do pgrep -f run_nest.sh >/dev/null || { echo NEST_CHAIN_GONE; break; }; sleep 30; done
.venv-tinker/bin/python scripts/stego/statetrack.py --profile gemma --label st_gemma_base > results/stego/gemma/st_base.log 2>&1 && echo ST_BASE_OK
.venv-tinker/bin/python scripts/stego/statetrack.py --profile gemma --label st_gemma_B --model-path v2g-B > results/stego/gemma/st_B.log 2>&1 && echo ST_B_OK
