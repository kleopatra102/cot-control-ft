#!/usr/bin/env bash
# After the acrostic chain: NEST encoding ladder (L0-L2 x 4,8,12,16 x answer/cot), base then B, 20 per cell.
cd /home/ola/dev/cot-control-ft
until grep -qE "B_OK|SERVER_FAILED" results/stego/gemma/chain.log; do sleep 30; done
grep -q SERVER_FAILED results/stego/gemma/chain.log && exit 2
.venv-tinker/bin/python scripts/stego/nest.py --profile gemma --label nest_gemma_base > results/stego/gemma/nest_base.log 2>&1 && echo NEST_BASE_OK
.venv-tinker/bin/python scripts/stego/nest.py --profile gemma --label nest_gemma_B --model-path v2g-B > results/stego/gemma/nest_B.log 2>&1 && echo NEST_B_OK
