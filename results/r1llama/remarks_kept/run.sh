#!/usr/bin/env bash
# Kept base measurement and remark build for R1-Distill-Llama-8B on its final draw (r1llama-2026-11-25d), own traces. Resumable.
cd /home/ola/dev/cot-control-ft; D=results/r1llama/remarks_kept; U=http://192.168.1.137:8000/v1
R="/home/ola/dev/cot-control-ft/.venv/bin/python scripts/sft_remarks.py"
[[ -f $D/rows.jsonl ]] || $R rows --dir $D --draw results/r1llama/prog_pool/draw.json --sources results/r1llama/sft/stage1_rollouts.jsonl || { echo STEP_FAILED rows; exit 3; }
if ! curl -s -m 3 $U/models | grep -q '"id"'; then
  ssh 192.168.1.202 'cd ~/dev/cot-control-ft && (MODEL=deepseek-ai/DeepSeek-R1-Distill-Llama-8B REASONING_PARSER=deepseek_r1 GPU_UTIL=0.90 MAX_LEN=16384 MAX_LORAS=1 EXTRA_ARGS="--quantization fp8" setsid nohup scripts/serve_vllm.sh > results/r1llama/serve_remarks.log 2>&1 < /dev/null &) ; sleep 2'
fi
for i in $(seq 1 60); do curl -s -m 3 $U/models | grep -q '"id"' && break; python3 -c "import time;time.sleep(8)"; done
$R sample --dir $D --config configs/r1llama.yaml --base-url $U --concurrency 48 && $R judge --dir $D || { echo STEP_FAILED sample-judge; exit 3; }
for k in 1 2 3; do
  n=$(python3 -c "import json;print(sum(not json.loads(l)['usable'] for l in open('$D/profiles.jsonl')))"); [[ $n == 0 ]] && break
  $R sample --dir $D --config configs/r1llama.yaml --base-url $U --retry $k && $R judge --dir $D
done
$R judge2 --dir $D || { echo STEP_FAILED judge2; exit 3; }
ssh skynet3 'pkill -f "[b]in/vllm serve"; sleep 12'      # the base server runs on skynet3 since 13:45 on 25 November
M=dev/cot-control-ft/tmp_scripts/mt_remarks2
$R mt-todo --dir $D && scp -q $D/mt_todo.json 192.168.1.202:$M/ \
 && ssh 192.168.1.202 "cd ~/dev/cot-control-ft && HF_HUB_OFFLINE=1 MT_DEVICE=cuda MT_BS=32 .venv/bin/python tmp_scripts/mt_remarks2/mt_remote.py" \
 && scp -q 192.168.1.202:$M/mt_done.json $D/mt_done.json && $R mt-merge --dir $D && $R mt-check --dir $D \
 && $R build --dir $D && $R report --dir $D && $R review --dir $D --n 50 && echo RUN_DONE || echo STEP_FAILED late
