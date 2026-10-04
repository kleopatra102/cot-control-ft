#!/usr/bin/env bash
# v2 conditions on gpt-oss-20b (CONDITIONS_V2.md, V2_GPTOSS_FINDINGS.md): train A, B, A1 (attention-only LoRA, one epoch,
# 554 examples each), then evaluate base, A, B, A1 on 40 rules x 6 templates x 20 questions. Idempotent; under gpu_supervisor.
set -uo pipefail
cd "$(dirname "$0")/../.."
R=results/v2_gptoss
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
for arm in A B A1; do
  ck=$R/ckpts/$arm
  [[ -f $ck/step-final/adapter_config.json ]] && continue
  log "train $arm"
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True UNSLOTH_COMPILE_DISABLE=1 TORCHDYNAMO_DISABLE=1 .venv-unsloth/bin/python scripts/train_lora_gptoss.py --max-len 4096 \
    --data data/sft/v2_gptoss_$arm.jsonl --out-dir $ck > $R/train_$arm.log 2>&1
  [[ -f $ck/step-final/adapter_config.json ]] || { log "train $arm FAILED"; tail -5 $R/train_$arm.log; exit 3; }
done
MODEL=openai/gpt-oss-20b REASONING_PARSER=openai_gptoss ATTN_BACKEND=TRITON_ATTN MAX_LEN=40960 MAX_LORAS=1 \
  scripts/serve_vllm.sh v2-A=$R/ckpts/A/step-final v2-B=$R/ckpts/B/step-final v2-A1=$R/ckpts/A1/step-final > $R/serve.log 2>&1 & SERVER=$!
until grep -qE "Application startup complete" $R/serve.log; do kill -0 $SERVER 2>/dev/null || { log "server died"; tail -5 $R/serve.log; exit 2; }; sleep 5; done
# smoke: a developer-message request (template T4) must be accepted and produce reasoning
.venv/bin/python - <<'PY' || { log "developer-role smoke test FAILED"; kill $SERVER; exit 4; }
from openai import OpenAI
c = OpenAI(base_url="http://localhost:8000/v1", api_key="x")
for m in ("openai/gpt-oss-20b", "v2-A"):
    r = c.chat.completions.create(model=m, max_tokens=2048, extra_body={"reasoning_effort": "medium"},
        messages=[{"role": "developer", "content": "Rule for your private reasoning: Write entirely in capital letters."}, {"role": "user", "content": "What is 2 + 3?"}])
    msg = r.choices[0].message; reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None) or ""
    print(m, "| reasoning:", repr(reasoning[:120]), "| answer:", repr((msg.content or "")[:40]))
    assert reasoning.strip(), "no reasoning returned"
PY
for m in base A B A1; do
  name=$([[ $m == base ]] && echo openai/gpt-oss-20b || echo v2-$m)
  [[ -f $R/eval/$m/.done ]] || { log "eval $m"; .venv/bin/python scripts/v2/run_eval.py --label $m --model $name 2>&1 | grep -vE "HTTP|it/s\]|s/it\]" | tail -3 && touch $R/eval/$m/.done; }
done
kill $SERVER; wait $SERVER 2>/dev/null; sleep 5
echo STAGE_V2_GPTOSS_DONE
