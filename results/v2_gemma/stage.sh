#!/usr/bin/env bash
# v2 conditions on Gemma-4-31B-IT (QAT 4-bit): base traces -> calibration -> base eval -> build A/B (API) -> audit ->
# size-match -> train A, B, A1 -> adapter check -> eval A, B, A1 -> report. Idempotent; run under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
export V2_RUN=gemma COTCTL_NO_ANSWER_TAG=1 V2_API=openai  # rewriter and judge via the OpenAI key (JUDGE_API_KEY), gpt-4.1
R=results/v2_gemma; M=google/gemma-4-31B-it-qat-w4a16-ct; CFG=configs/gemma4.yaml; TH=data/v2_thresholds_gemma-4-31b.json
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
F() { grep -vE "HTTP|it/s\]|s/it\]" | tail -${1:-3}; }
SERVER=""
serve() {  # serve [adapters...]; tries fp8 KV first, then a smaller bf16 configuration
  for cfgset in "KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN MAX_LEN=16384 GPU_UTIL=0.92" "MAX_LEN=14336 GPU_UTIL=0.95"; do
    log "serve ($cfgset) $*"
    env $cfgset MODEL=$M REASONING_PARSER=gemma4 MAX_SEQS=32 MAX_LORAS=1 EXTRA_ARGS='--limit-mm-per-prompt {"image":0,"audio":0}' \
      scripts/serve_vllm.sh "$@" > $R/serve.log 2>&1 & SERVER=$!
    until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || break; sleep 5; done
    if kill -0 $SERVER 2>/dev/null; then return 0; fi
    log "server failed with ($cfgset):"; grep -E "Error|error" $R/serve.log | tail -3
  done
  log "SERVER FAILED (both configurations)"; exit 2
}
stop() { [[ -n "$SERVER" ]] && { kill $SERVER; wait $SERVER 2>/dev/null; sleep 5; SERVER=""; }; }

# 0. weights present
for repo in google/gemma-4-31B-it-qat-w4a16-ct unsloth/gemma-4-31B-it-qat-q4_0-unquantized; do
  .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('$repo', local_files_only=True)" >/dev/null 2>&1 || { log "weights for $repo not fully downloaded"; exit 5; }
done

# 1. base: smoke, stage-1 traces, calibration, base eval
if [[ ! -f $R/eval/base/.done ]]; then
  serve
  .venv/bin/python - <<'PY' || { log "THINKING SMOKE TEST FAILED"; stop; exit 4; }
from openai import OpenAI
c = OpenAI(base_url="http://localhost:8000/v1", api_key="x")
for msgs in ([{"role": "user", "content": "What is 17 * 3? Think it through."}],
             [{"role": "developer", "content": "Rule for your private reasoning: Write entirely in capital letters."}, {"role": "user", "content": "What is 2 + 3?"}]):
    r = c.chat.completions.create(model="google/gemma-4-31B-it-qat-w4a16-ct", max_tokens=3000, temperature=1.0, top_p=0.95,
                                  extra_body={"top_k": 64, "chat_template_kwargs": {"enable_thinking": True}}, messages=msgs)
    m = r.choices[0].message; rs = getattr(m, "reasoning", None) or getattr(m, "reasoning_content", None) or ""
    print("reasoning:", repr(rs[:150]), "| answer:", repr((m.content or "")[:60]))
    assert rs.strip(), "no separate reasoning returned"
    assert "<|channel>" not in (m.content or "") and "thought\n" not in (m.content or "")[:20], "thinking leaked into the answer"
PY
  [[ -f $R/.done_stage1 ]] || { log "stage1 base traces"; .venv/bin/python scripts/build_sft.py --stage 1 --config $CFG --n-rows 937 --out-dir $R/sft 2>&1 | F && touch $R/.done_stage1; }
  [[ -f $TH ]] || { log "calibrate"; .venv/bin/python scripts/v2/calibrate.py --traces $R/sft/stage1_rollouts.jsonl --out $TH 2>&1 | F 4; }
  [[ -f $TH ]] || { log "CALIBRATION FAILED"; stop; exit 3; }
  log "eval base"; .venv/bin/python scripts/v2/run_eval.py --label base --model $M --max-tokens 12288 2>&1 | F && touch $R/eval/base/.done
  stop
fi

# 2. training data (API), audit, size match
[[ -s data/sft/v2_gemma_B.jsonl && -s data/sft/v2_gemma_A1.jsonl ]] || { log "build A, B"; .venv/bin/python scripts/v2/build_data.py --arms A,B --n-rows 937 > $R/build.log 2>&1; grep -E "^arm|Error" $R/build.log | tail -4; }
[[ -s data/sft/v2_gemma_B.jsonl ]] || { log "BUILD FAILED"; tail -5 $R/build.log; exit 3; }
[[ -f $R/audit.json ]] || { log "audit"; .venv/bin/python scripts/v2/audit.py --arms A,B > $R/audit.log 2>&1; grep -E "FLAG|rows;" $R/audit.log | head -20; }
[[ -f data/sft/v2_gemma_A_full.jsonl ]] || .venv/bin/python - <<'PY'
import json, random, shutil
for arm in ("A", "A1"): shutil.copy(f"data/sft/v2_gemma_{arm}.jsonl", f"data/sft/v2_gemma_{arm}_full.jsonl")
A = [json.loads(l) for l in open("data/sft/v2_gemma_A_full.jsonl")]; nB = sum(1 for _ in open("data/sft/v2_gemma_B.jsonl"))
keep = set(x["idx"] for x in random.Random("v2-size-match").sample(A, min(nB, len(A))))
for arm in ("A", "A1"):
    rows = [json.loads(l) for l in open(f"data/sft/v2_gemma_{arm}_full.jsonl") if json.loads(l)["idx"] in keep]
    open(f"data/sft/v2_gemma_{arm}.jsonl", "w").write("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)); print(arm, len(rows), "rows (B has", nB, ")")
PY

# 3. training
for arm in A B A1; do
  ck=$R/ckpts/$arm
  [[ -f $ck/step-final/adapter_config.json ]] && continue
  log "train $arm"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_gemma.py \
    --data data/sft/v2_gemma_$arm.jsonl --out-dir $ck > $R/train_$arm.log 2>&1
  [[ -f $ck/step-final/adapter_config.json ]] || { log "TRAIN $arm FAILED"; tail -8 $R/train_$arm.log; exit 3; }
done

# 4. adapters: must change outputs (vLLM silently ignored adapters on Qwen3.5), then evaluate
serve v2g-A=$R/ckpts/A/step-final v2g-B=$R/ckpts/B/step-final v2g-A1=$R/ckpts/A1/step-final
.venv/bin/python - <<'PY' || { log "ADAPTER CHECK FAILED: adapters do not change outputs"; stop; exit 4; }
from openai import OpenAI
c = OpenAI(base_url="http://localhost:8000/v1", api_key="x")
qs = ["Think step-by-step. Format your reasoning according to the following rule: **Write entirely in capital letters.**\n\nHere is the question:\n\nWhat is 12 + 30?",
      "Think step-by-step. Format your reasoning according to the following rule: **Do not use any commas.**\n\nHere is the question:\n\nName three primary colours."]
diff = 0
for q in qs:
    outs = {}
    for m in ("google/gemma-4-31B-it-qat-w4a16-ct", "v2g-A"):
        r = c.chat.completions.create(model=m, max_tokens=600, temperature=0.0, extra_body={"chat_template_kwargs": {"enable_thinking": True}}, messages=[{"role": "user", "content": q}])
        msg = r.choices[0].message; outs[m] = (getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or "") + (msg.content or "")
    diff += outs["google/gemma-4-31B-it-qat-w4a16-ct"] != outs["v2g-A"]; print("base:", repr(outs["google/gemma-4-31B-it-qat-w4a16-ct"][:90])); print("A:   ", repr(outs["v2g-A"][:90]))
assert diff > 0, "identical greedy outputs with and without the adapter"
PY
for arm in A B A1; do
  [[ -f $R/eval/$arm/.done ]] || { log "eval $arm"; .venv/bin/python scripts/v2/run_eval.py --label $arm --model v2g-$arm --max-tokens 12288 2>&1 | F && touch $R/eval/$arm/.done; }
done
stop
.venv/bin/python scripts/v2/report.py > $R/report.log 2>&1; .venv/bin/python scripts/v2/report_more.py >> $R/report.log 2>&1; tail -14 $R/report.log
echo STAGE_V2_GEMMA_DONE
