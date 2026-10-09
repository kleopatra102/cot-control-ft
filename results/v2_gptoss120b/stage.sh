#!/usr/bin/env bash
# v2 conditions on gpt-oss-120b via Tinker, within-family arm (B) only: base traces -> calibration -> base eval ->
# build B (gpt-4.1) -> audit -> LoRA on Tinker -> eval B -> report. No local GPU. Idempotent.
set -uo pipefail
cd "$(dirname "$0")/../.."
export V2_RUN=gptoss120b COTCTL_NO_ANSWER_TAG=1 V2_API=openai
R=results/v2_gptoss120b; TH=data/v2_thresholds_gpt-oss-120b.json; PY=.venv-tinker/bin/python
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
F() { grep -vE "HTTP|it/s\]|s/it\]|Warning|super\(\)" | tail -${1:-3}; }
mkdir -p $R/sft
if [[ ! -f $R/.done_stage1 ]]; then
  log "stage1 base traces (Tinker)"
  $PY - <<'PY' 2>&1 | F && touch $R/.done_stage1
import json, sys
sys.path.insert(0, "src")
from dotenv import load_dotenv; load_dotenv(".env")
from cotctl.tinker_client import TinkerClient
from cotctl.inference import Request, RolloutStore, SamplingParams, run_sync
qs, seen = [], set()
for l in open("results/gptoss/sft/stage1_rollouts.jsonl"):  # the v2 stage-1 question pool (937 questions)
    r = json.loads(l); q = r["prompt"].split("Here is the question:\n\n", 1)[-1].strip()
    if q not in seen: seen.add(q); qs.append((r["sample_id"], q))
reqs = [Request(sample_id=sid, mode="plain", prompt=f"Think step-by-step.\n\nHere is the question:\n\n{q}") for sid, q in qs]
c = TinkerClient("openai/gpt-oss-120b", "gpt_oss_medium_reasoning", concurrency=64)
st = RolloutStore("results/v2_gptoss120b/sft/stage1_rollouts.jsonl")
with st: run_sync(c, reqs, SamplingParams(max_tokens=12288, temperature=1.0, top_p=1.0, top_k=None), st, desc="stage1")
rows = list(st.read_all()); print(len(rows), "traces;", sum(r["think_status"] == "ok" for r in rows), "ok")
PY
fi
[[ -f $TH ]] || { log "calibrate"; $PY scripts/v2/calibrate.py --traces $R/sft/stage1_rollouts.jsonl --out $TH 2>&1 | F 4; }
[[ -f $R/eval/base/.done ]] || { log "eval base"; $PY scripts/v2/run_eval.py --label base --model openai/gpt-oss-120b --max-tokens 12288 2>&1 | F && touch $R/eval/base/.done; }
[[ -s data/sft/v2_gptoss120b_B.jsonl ]] || { log "build B"; $PY scripts/v2/build_data.py --arms B --n-rows 937 > $R/build.log 2>&1; grep -E "^arm|Error" $R/build.log | tail -3; }
[[ -s data/sft/v2_gptoss120b_B.jsonl ]] || { log "BUILD FAILED"; tail -5 $R/build.log; exit 3; }
[[ -f $R/audit.json ]] || { log "audit"; $PY scripts/v2/audit.py --arms B > $R/audit.log 2>&1; grep -E "FLAG|rows;" $R/audit.log | head -12; }
[[ -f $R/gptoss120b/ckpt_B.json ]] || { log "train B (Tinker)"; $PY scripts/v2/train_tinker.py --key gptoss120b --name B --data data/sft/v2_gptoss120b_B.jsonl --out-root $R > $R/train_B.log 2>&1; grep -E "examples|saved|Error" $R/train_B.log | tail -3; }
[[ -f $R/gptoss120b/ckpt_B.json ]] || { log "TRAIN B FAILED"; tail -8 $R/train_B.log; exit 3; }
P=$($PY -c "import json; print(json.load(open('$R/gptoss120b/ckpt_B.json'))['sampler_path'])")
[[ -f $R/eval/B/.done ]] || { log "eval B"; $PY scripts/v2/run_eval.py --label B --model gptoss120b-B --model-path "$P" --max-tokens 12288 2>&1 | F && touch $R/eval/B/.done; }
.venv/bin/python scripts/v2/report.py > $R/report.log 2>&1; .venv/bin/python scripts/v2/report_more.py >> $R/report.log 2>&1; tail -10 $R/report.log
echo STAGE_V2_GPTOSS120B_DONE
