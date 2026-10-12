#!/usr/bin/env bash
# v2 conditions on Qwen3.8-27B via Tinker, within-family arm (B) only, T1-T3 eval: base traces (thresholds and base scores come from screening) ->
# build B (gpt-4.1) -> audit -> LoRA on Tinker -> eval B on the screening grid (base numbers: results/screen_v2/qwen38_tinker). No local GPU. Idempotent.
set -uo pipefail
cd "$(dirname "$0")/../.."
export V2_RUN=qwen38 COTCTL_NO_ANSWER_TAG=1 V2_API=openai
R=results/v2_qwen38; TH=data/v2_thresholds_qwen3.8-27b.json; PY=.venv-tinker/bin/python
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
c = TinkerClient("Qwen/Qwen3.8-27B", "qwen3_8_medium_reasoning", concurrency=64)
st = RolloutStore("results/v2_qwen38/sft/stage1_rollouts.jsonl")
with st: run_sync(c, reqs, SamplingParams(max_tokens=12288, temperature=1.0, top_p=0.95, top_k=20), st, desc="stage1")
rows = list(st.read_all()); print(len(rows), "traces;", sum(r["think_status"] == "ok" for r in rows), "ok")
PY
fi
[[ -s data/sft/v2_qwen38_B.jsonl ]] || { log "build B"; $PY scripts/v2/build_data.py --arms B --n-rows 937 > $R/build.log 2>&1; grep -E "^arm|Error" $R/build.log | tail -3; }
[[ -s data/sft/v2_qwen38_B.jsonl ]] || { log "BUILD FAILED"; tail -5 $R/build.log; exit 3; }
[[ -f $R/audit.json ]] || { log "audit"; $PY scripts/v2/audit.py --arms B > $R/audit.log 2>&1; grep -E "FLAG|rows;" $R/audit.log | head -12; }
[[ -f $R/qwen38_tinker/ckpt_B.json ]] || { log "train B (Tinker)"; $PY scripts/v2/train_tinker.py --key qwen38_tinker --name B --data data/sft/v2_qwen38_B.jsonl --out-root $R > $R/train_B.log 2>&1; grep -E "examples|saved|Error" $R/train_B.log | tail -3; }
[[ -f $R/qwen38_tinker/ckpt_B.json ]] || { log "TRAIN B FAILED"; tail -8 $R/train_B.log; exit 3; }
P=$($PY -c "import json; print(json.load(open('$R/qwen38_tinker/ckpt_B.json'))['sampler_path'])")
[[ -f results/screen_v2/qwen38_B/summary.json ]] || { log "eval B (screening grid, 1 sample, base thresholds)"; V2_RUN=gptoss $PY scripts/v2/screen.py --name qwen38_B --model Qwen/Qwen3.8-27B --backend tinker --renderer qwen3_8_medium_reasoning --model-path "$P" --thresholds $TH --samples 1 --sampling '{"temperature":1.0,"top_p":0.95,"top_k":20}' > $R/eval_B.log 2>&1; tail -3 $R/eval_B.log; }
echo STAGE_V2_QWEN38_DONE
