#!/usr/bin/env python3
"""QLoRA SFT for Gemma-4-31B-IT (v2 experiment) through Unsloth: same recipe as the other v2 arms (r 32, alpha 32,
lr 1e-4, Adam (0.9, 0.95), batch 1 x grad-accum 4, one epoch, checkpoints at step 60 and step-final).

Base: the bf16 copy of Google's QAT weights (unsloth/gemma-4-31B-it-qat-q4_0-unquantized), quantised to 4-bit on load,
so the adapter is trained on the same weights it is served on (google/gemma-4-31B-it-qat-w4a16-ct).
LoRA on the language model only (attention + MLP); the vision tower is untouched.

Rows are {"messages": [developer?, user, assistant]} with the assistant content "<think>\\n{reasoning}\\n</think>\\n\\n{answer}".
They are rendered with Gemma's chat template, thinking on: a developer message becomes the system turn, the reasoning
goes in the thought channel (<|channel>thought ... <channel|>), and the loss covers the model turn only. Gemma soft-caps
its output logits (final_logit_softcapping = 30), so the chunked loss applies the same cap.

  .venv-unsloth/bin/python scripts/train_lora_gemma.py --data data/sft/v2_gemma_A.jsonl --out-dir results/v2_gemma/ckpts/A
"""
from __future__ import annotations
import argparse, json, math, random, re, time
from pathlib import Path
import unsloth  # noqa: F401
from unsloth import FastModel
import torch

THINK_RE = re.compile(r"^<think>\n?(.*?)\n?</think>\s*(.*)$", re.DOTALL)


def to_gemma(messages):
    out = []
    for m in messages:
        if m["role"] in ("developer", "system"): out.append({"role": "system", "content": m["content"]})
        elif m["role"] == "user": out.append({"role": "user", "content": m["content"]})
        else:
            mm = THINK_RE.match(m["content"]); thinking, answer = (mm.group(1), mm.group(2).strip()) if mm else ("", m["content"])
            out.append({"role": "assistant", "content": answer, "reasoning_content": thinking})
    return out


def encode(tok, messages, max_len):
    msgs = to_gemma(messages)
    full = tok.apply_chat_template(msgs, tokenize=False, enable_thinking=True)
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True, enable_thinking=True)
    assert full.startswith(prompt), "prompt is not a prefix of the rendered example"
    assert "<|channel>thought" in full[len(prompt):], "reasoning was not rendered into the thought channel"
    ids = tok(full, add_special_tokens=False)["input_ids"]
    if len(ids) > max_len: return None
    n = len(tok(prompt, add_special_tokens=False)["input_ids"])
    return ids, [-100] * n + ids[n:]


def text_model(model):
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    inner = base.model
    return base, (inner.language_model if hasattr(inner, "language_model") else inner)


def chunked_loss(model, x, y, cap, chunk=512):
    import torch.nn.functional as F
    base, lm = text_model(model)
    h = lm(input_ids=x, use_cache=False).last_hidden_state[:, :-1, :]
    h = h.reshape(-1, h.size(-1)); y = y[:, 1:].reshape(-1)
    head = base.lm_head if hasattr(base, "lm_head") else base.get_output_embeddings()
    tot = h.new_zeros((), dtype=torch.float32); n = (y != -100).sum()
    for i in range(0, h.size(0), chunk):
        yy = y[i:i + chunk]
        if not (yy != -100).any(): continue
        logits = head(h[i:i + chunk].to(head.weight.dtype)).float()
        if cap: logits = cap * torch.tanh(logits / cap)
        tot = tot + F.cross_entropy(logits, yy, ignore_index=-100, reduction="sum")
    return tot / n.clamp(min=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default="unsloth/gemma-4-31B-it-qat-q4_0-unquantized"); ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--rank", type=int, default=32); ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42); ap.add_argument("--save-steps", default="60"); ap.add_argument("--smoke", type=int, default=0)
    a = ap.parse_args(); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); random.seed(a.seed); torch.manual_seed(a.seed)
    model, tok = FastModel.from_pretrained(a.model, max_seq_length=a.max_len, load_in_4bit=True, dtype=None)
    tok = getattr(tok, "tokenizer", tok)
    model = FastModel.get_peft_model(model, finetune_vision_layers=False, finetune_language_layers=True, finetune_attention_modules=True,
                                     finetune_mlp_modules=True, r=a.rank, lora_alpha=a.rank, lora_dropout=0.0, bias="none",
                                     use_gradient_checkpointing="unsloth", random_state=a.seed)
    cfg = model.config; tc = getattr(cfg, "text_config", cfg); cap = getattr(tc, "final_logit_softcapping", None)
    print(f"trainable params {sum(p.numel() for p in model.parameters() if p.requires_grad)/1e6:.1f}M; final_logit_softcapping={cap}", flush=True)
    ex, dropped = [], 0
    for l in open(a.data):
        if not l.strip(): continue
        e = encode(tok, json.loads(l)["messages"], a.max_len)
        if e is None: dropped += 1
        else: ex.append(e)
    random.shuffle(ex); total = math.ceil(len(ex) / a.grad_accum)
    if a.smoke: total = min(total, a.smoke)
    saves = sorted({int(s) for s in a.save_steps.split(",") if s} | {total})
    print(f"{len(ex)} examples ({dropped} over {a.max_len} tokens dropped) -> {total} optimizer steps; checkpoints at {saves}", flush=True)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0); model.train()
    log = open(out / "train_metrics.jsonl", "w"); t0 = time.time(); i = 0
    for step in range(1, total + 1):
        opt.zero_grad(set_to_none=True); ls = 0.0; k = 0
        for _ in range(a.grad_accum):
            if i >= len(ex): break
            ids, lab = ex[i]; i += 1
            loss = chunked_loss(model, torch.tensor([ids], device="cuda"), torch.tensor([lab], device="cuda"), cap)
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
