#!/usr/bin/env python3
"""Haskins-style synthetic document finetuning (SDF) for Gemma-4-31B-IT, continuing a QLoRA adapter.

Raw documents, no chat template: <bos> + "<|doc|>" + text, loss masked over <bos> and the "<|doc|>" prefix (Haskins'
train_sdft.py convention). Same model, quantisation, LoRA shape (attention + MLP, r 32) and soft-capped chunked loss
as scripts/train_lora_gemma.py, which trained the v2 adapter this continues. Batch 1 x grad-accum 8 (= his batch 8).

    .venv-unsloth/bin/python scripts/haskins/train_sdf_gemma.py --data D/train.jsonl --init-adapter A --out-dir O --lr 1e-4
"""
from __future__ import annotations
import argparse, json, math, random, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "scripts"))
import unsloth  # noqa: F401
from unsloth import FastModel
import torch
from train_lora_gemma import chunked_loss  # noqa: E402

DOC = "<|doc|>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out-dir", required=True); ap.add_argument("--init-adapter", required=True)
    ap.add_argument("--lr", type=float, required=True); ap.add_argument("--epochs", type=int, default=1); ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=2048); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--smoke", type=int, default=0)
    a = ap.parse_args(); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); random.seed(a.seed); torch.manual_seed(a.seed)
    model, tok = FastModel.from_pretrained(a.init_adapter, max_seq_length=a.max_len, load_in_4bit=True, dtype=None)  # base + adapter
    tok = getattr(tok, "tokenizer", tok)
    FastModel.for_training(model)
    for n, p in model.named_parameters(): p.requires_grad = "lora_" in n
    params = [p for p in model.parameters() if p.requires_grad]
    cfg = model.config; tc = getattr(cfg, "text_config", cfg); cap = getattr(tc, "final_logit_softcapping", None)
    print(f"trainable params {sum(p.numel() for p in params)/1e6:.1f}M (from {a.init_adapter}); softcap={cap}", flush=True)
    pre = [tok.bos_token_id] + tok(DOC, add_special_tokens=False)["input_ids"]
    ex = []
    for l in open(a.data):
        ids = tok(json.loads(l)["text"], add_special_tokens=False)["input_ids"][: a.max_len - len(pre)]
        ex.append((pre + ids, [-100] * len(pre) + ids))
    total = math.ceil(len(ex) * a.epochs / a.grad_accum)
    if a.smoke: total = min(total, a.smoke)
    print(f"{len(ex)} documents x {a.epochs} epoch(s) -> {total} optimizer steps (batch {a.grad_accum})", flush=True)
    opt = torch.optim.AdamW(params, lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0); model.train()
    order = [e for _ in range(a.epochs) for e in random.sample(ex, len(ex))]
    log = open(out / "train_metrics.jsonl", "w"); t0 = time.time(); i = 0
    for step in range(1, total + 1):
        opt.zero_grad(set_to_none=True); ls = 0.0; k = 0
        for _ in range(a.grad_accum):
            if i >= len(order): break
            ids, lab = order[i]; i += 1
            loss = chunked_loss(model, torch.tensor([ids], device="cuda"), torch.tensor([lab], device="cuda"), cap)
            (loss / a.grad_accum).backward(); ls += loss.item(); k += 1
        torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step()
        rec = {"step": step, "loss": round(ls / max(1, k), 4), "seconds": round(time.time() - t0, 1), "max_mem_gb": round(torch.cuda.max_memory_allocated() / 2**30, 1)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if step % 5 == 0 or step == 1: print(rec, flush=True)
    model.save_pretrained(out / "step-final"); tok.save_pretrained(out / "step-final")
    print(f"saved {out / 'step-final'}; {total} steps in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
