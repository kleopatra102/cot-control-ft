#!/usr/bin/env python3
"""QLoRA SFT for Qwen3.8-27B through Unsloth (4-bit base), same recipe as scripts/train_lora.py otherwise:
r 32, alpha 32, lr 1e-4, Adam (0.9, 0.95), bs 1 x grad-accum 4, one epoch, checkpoints at step 60 and step-final.

LoRA targets every linear in the language model (attention, linear-attention projections, MLP); vision tower and
MTP head excluded, as in the Qwen3.5-9B run. Rows are the repo's {"messages": [user, assistant]} with the assistant
content "<think>\\n...\\n</think>\\n\\n{answer}", rendered through the model's chat template; loss on assistant tokens.

  .venv-unsloth/bin/python scripts/train_lora_unsloth_qwen.py --data data/sft/q38_Q5.jsonl --out-dir results/qwen38/ckpts/Q5
"""
from __future__ import annotations
import argparse, json, math, random, re, sys, time
from pathlib import Path
import unsloth  # noqa: F401
from unsloth import FastLanguageModel
import torch

REPO = Path(__file__).resolve().parents[1]
TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj", "gate_proj", "up_proj", "down_proj"]
HEADER = "<|im_start|>assistant\n"


def encode(tok, messages, max_len):
    full = tok.apply_chat_template(messages, tokenize=False)
    i = full.rfind(HEADER)
    assert i >= 0, "assistant header not found"
    prompt = full[: i + len(HEADER)]
    ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(ids) > max_len: return None
    n = len(tok(prompt, add_special_tokens=False)["input_ids"])
    return ids, [-100] * n + ids[n:]


def chunked_loss(model, x, y, chunk=1024):
    import torch.nn.functional as F
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    lm = base.model.language_model if hasattr(base.model, "language_model") else base.model
    h = lm(input_ids=x, use_cache=False).last_hidden_state[:, :-1, :].reshape(-1, base.lm_head.in_features)
    y = y[:, 1:].reshape(-1); tot = h.new_zeros((), dtype=torch.float32); n = (y != -100).sum()
    for i in range(0, h.size(0), chunk):
        yy = y[i:i + chunk]
        if (yy != -100).any(): tot = tot + F.cross_entropy(base.lm_head(h[i:i + chunk].to(base.lm_head.weight.dtype)).float(), yy, ignore_index=-100, reduction="sum")
    return tot / n.clamp(min=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="unsloth/Qwen3.8-27B-unsloth-bnb-4bit"); ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--rank", type=int, default=32); ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42); ap.add_argument("--save-steps", default="60"); ap.add_argument("--smoke", type=int, default=0)
    a = ap.parse_args(); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); random.seed(a.seed); torch.manual_seed(a.seed)
    model, tok = FastLanguageModel.from_pretrained(a.model, max_seq_length=a.max_len, load_in_4bit=True, dtype=None)
    tok = getattr(tok, "tokenizer", tok)
    model = FastLanguageModel.get_peft_model(model, r=a.rank, lora_alpha=a.rank, lora_dropout=0.0, bias="none", target_modules=TARGETS,
                                             use_gradient_checkpointing="unsloth", random_state=a.seed)
    print(f"trainable params {sum(p.numel() for p in model.parameters() if p.requires_grad)/1e6:.1f}M", flush=True)
    ex, dropped = [], 0
    for l in open(a.data):
        if not l.strip(): continue
        e = encode(tok, json.loads(l)["messages"], a.max_len)
        if e is None: dropped += 1
        else: ex.append(e)
    random.shuffle(ex); total = math.ceil(len(ex) / a.grad_accum)
    if a.smoke: total = min(total, a.smoke)
    saves = sorted({int(s) for s in a.save_steps.split(",") if s} | {total})
    print(f"{len(ex)} examples ({dropped} over {a.max_len} dropped) -> {total} steps; checkpoints {saves}", flush=True)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0); model.train()
    log = open(out / "train_metrics.jsonl", "w"); t0 = time.time(); i = 0
    for step in range(1, total + 1):
        opt.zero_grad(set_to_none=True); ls = 0.0; k = 0
        for _ in range(a.grad_accum):
            if i >= len(ex): break
            ids, lab = ex[i]; i += 1
            loss = chunked_loss(model, torch.tensor([ids], device="cuda"), torch.tensor([lab], device="cuda"))
            (loss / a.grad_accum).backward(); ls += loss.item(); k += 1
        torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step()
        rec = {"step": step, "loss": ls / max(1, k), "seconds": round(time.time() - t0, 1), "max_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if step % 10 == 0 or step == 1: print(rec, flush=True)
        if step in saves:
            name = "step-final" if step == total else f"step-{step}"; model.save_pretrained(out / name); tok.save_pretrained(out / name); print("saved", name, flush=True)
    print(f"done: {total} steps in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
