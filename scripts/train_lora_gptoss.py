#!/usr/bin/env python3
"""LoRA SFT for gpt-oss-20b through Unsloth (4-bit base), attention-only adapter (GPTOSS_PLAN.md).

Why a separate trainer: transformers cannot train through gpt-oss's MXFP4 experts and the bf16 model (~41 GB) does not
fit the 5090. Unsloth loads a 4-bit base that fits; the adapter covers q/k/v/o only, so it serves directly on top of
the original MXFP4 model in vLLM (whose gpt-oss LoRA mapping covers attention only). Same recipe otherwise as
scripts/train_lora.py: r 32, alpha 32, lr 1e-4, Adam (0.9, 0.95), bs 1 x grad-accum 4, one epoch, max_len 8192,
checkpoints at step 60 and step-final.

Rows are the repo's standard {"messages": [user, assistant]} with the assistant content
"<think>\\n{reasoning}\\n</think>\\n\\n{answer}". They are rendered in gpt-oss's harmony format: reasoning in the
analysis channel, answer in the final channel, system prompt with "Reasoning: medium" as vLLM serves it. Loss on
the assistant tokens only.

Run with the Unsloth environment:  .venv-unsloth/bin/python scripts/train_lora_gptoss.py --data ... --out-dir ...
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
from pathlib import Path

import unsloth  # noqa: F401  (must be imported before transformers/peft)
from unsloth import FastLanguageModel
import torch

THINK_RE = re.compile(r"^<think>\n?(.*?)\n?</think>\s*(.*)$", re.DOTALL)


def to_harmony(messages):
    user, asst = messages[0]["content"], messages[-1]["content"]
    m = THINK_RE.match(asst)
    thinking, answer = (m.group(1), m.group(2).strip()) if m else ("", asst)
    return [{"role": "user", "content": user}, {"role": "assistant", "thinking": thinking, "content": answer}]


def encode(tok, messages, max_len, effort):
    msgs = to_harmony(messages)
    full = tok.apply_chat_template(msgs, tokenize=False, reasoning_effort=effort)
    prompt = tok.apply_chat_template(msgs[:1], tokenize=False, add_generation_prompt=True, reasoning_effort=effort)
    assert full.startswith(prompt), "prompt is not a prefix of the rendered example"
    ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(ids) > max_len:
        return None
    n_prompt = len(tok(prompt, add_special_tokens=False)["input_ids"])
    return ids, [-100] * n_prompt + ids[n_prompt:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="unsloth/gpt-oss-20b")
    ap.add_argument("--max-len", type=int, default=8192); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32); ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--effort", default="medium"); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save-steps", default="60"); ap.add_argument("--smoke", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    random.seed(a.seed); torch.manual_seed(a.seed)

    model, tok = FastLanguageModel.from_pretrained(a.model, max_seq_length=a.max_len, load_in_4bit=True, dtype=None)
    model = FastLanguageModel.get_peft_model(model, r=a.rank, lora_alpha=a.rank, lora_dropout=0.0, bias="none",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                                             use_gradient_checkpointing="unsloth", random_state=a.seed)
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"trainable params {n_train/1e6:.1f}M (attention-only LoRA r={a.rank})", flush=True)

    rows = [json.loads(l) for l in open(a.data) if l.strip()]
    ex, dropped = [], 0
    for r in rows:
        e = encode(tok, r["messages"], a.max_len, a.effort)
        if e is None: dropped += 1
        else: ex.append(e)
    random.shuffle(ex)
    total = math.ceil(len(ex) / a.grad_accum)
    if a.smoke: total = min(total, a.smoke)
    saves = sorted({int(s) for s in a.save_steps.split(",") if s} | {total})
    print(f"{len(ex)} examples ({dropped} over {a.max_len} tokens dropped) -> {total} optimizer steps; checkpoints at {saves}", flush=True)

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0)
    model.train(); log = open(out / "train_metrics.jsonl", "w"); t0 = time.time(); i = 0
    for step in range(1, total + 1):
        opt.zero_grad(set_to_none=True); loss_sum = 0.0; ntok = 0
        for _ in range(a.grad_accum):
            if i >= len(ex): break
            ids, labels = ex[i]; i += 1
            x = torch.tensor([ids], device="cuda"); y = torch.tensor([labels], device="cuda")
            o = model(input_ids=x, labels=y)
            (o.loss / a.grad_accum).backward(); loss_sum += o.loss.item(); ntok += 1
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        rec = {"step": step, "loss": loss_sum / max(1, ntok), "seconds": round(time.time() - t0, 1), "max_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if step % 10 == 0 or step == 1: print(rec, flush=True)
        if step in saves:
            name = "step-final" if step == total else f"step-{step}"
            model.save_pretrained(out / name); tok.save_pretrained(out / name); print(f"saved {name}", flush=True)
    print(f"done: {total} steps in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
