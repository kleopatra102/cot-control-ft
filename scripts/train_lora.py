#!/usr/bin/env python3
"""Run the LoRA SFT (P3).

    python scripts/train_lora.py                 # full run, W&B online
    python scripts/train_lora.py --smoke 8       # 8 steps, offline, to prove the loop works

Saves adapters at steps 60/120/180/final under results/ckpts/step-*/ and logs each as a W&B
artifact with that step's metrics attached, so a checkpoint's number and its weights cannot
drift apart.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO / ".env")

from cotctl.train.data import IGNORE_INDEX, collate, load_examples  # noqa: E402
from cotctl.train.sft_lora import (  # noqa: E402
    TrainConfig, chunked_causal_loss, dataset_fingerprint, target_module_names,
)

log = logging.getLogger("train")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--max-len", type=int, default=None)
    ap.add_argument("--smoke", type=int, default=0, help="stop after N optimizer steps")
    ap.add_argument("--wandb-mode", default=None, help="online | offline | disabled")
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--loss-chunk", type=int, default=512,
                    help="sequence positions per LM-head chunk; lower if memory is tight")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    cfg = TrainConfig()
    if args.data: cfg.data = args.data
    if args.out_dir: cfg.out_dir = args.out_dir
    if args.lr: cfg.lr = args.lr
    if args.max_len: cfg.max_len = args.max_len
    if args.wandb_mode: cfg.wandb_mode = args.wandb_mode
    if args.smoke:
        cfg.wandb_mode = cfg.wandb_mode or "offline"

    torch.manual_seed(cfg.seed)
    out_root = Path(cfg.out_dir); out_root.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(cfg.model)
    examples, data_stats = load_examples(REPO / cfg.data, tok, cfg.max_len)
    if args.smoke:
        examples = examples[: args.smoke * cfg.effective_batch]

    steps_per_epoch = math.ceil(len(examples) / cfg.effective_batch)
    total_steps = steps_per_epoch * cfg.epochs
    ckpt_steps = sorted(set(list(cfg.checkpoint_steps) + [total_steps]))
    ckpt_steps = [s for s in ckpt_steps if s <= total_steps]
    log.info("%d examples -> %d optimizer steps; checkpoints at %s", len(examples), total_steps, ckpt_steps)

    # --- W&B -------------------------------------------------------------
    if cfg.wandb_mode:
        os.environ["WANDB_MODE"] = cfg.wandb_mode
    import wandb

    run_name = args.run_name or f"qwen3.5-9b-r{cfg.lora_r}-lr{cfg.lr:g}-{time.strftime('%Y%m%d-%H%M%S')}"
    wandb_run = wandb.init(
        project=cfg.wandb_project, name=run_name,
        config={**{k: v for k, v in vars(cfg).items()},
                "dataset_sha256_16": dataset_fingerprint(REPO / cfg.data),
                "n_examples": len(examples), "total_steps": total_steps,
                "data_stats": {k: v for k, v in data_stats.items() if k != "dropped"}},
    )

    # Dataset visualisations, logged once: length and supervision distributions, and the
    # per-mode counts that the training curve is later broken down by.
    try:
        import wandb as _wb
        tbl = _wb.Table(columns=["row_idx", "mode", "tokens", "supervised", "masked_fraction"])
        for e in examples:
            tbl.add_data(e.row_idx, e.mode, len(e.input_ids), e.n_supervised, round(e.masked_fraction, 4))
        wandb.log({
            "data/examples": tbl,
            "data/seq_len_hist": _wb.Histogram([len(e.input_ids) for e in examples]),
            "data/supervised_hist": _wb.Histogram([e.n_supervised for e in examples]),
            "data/masked_fraction_hist": _wb.Histogram([e.masked_fraction for e in examples]),
        }, step=0)
    except Exception as e:  # noqa: BLE001 - never let logging kill the run
        log.warning("dataset logging failed: %s", e)

    # --- model -----------------------------------------------------------
    log.info("loading %s", cfg.model)
    model = AutoModelForCausalLM.from_pretrained(cfg.model, dtype=torch.bfloat16, device_map="cuda")
    model.config.use_cache = False
    targets = target_module_names(model)
    log.info("LoRA targets: %d linear modules (vision/MTP/lm_head excluded)", len(targets))

    model = get_peft_model(model, LoraConfig(
        r=cfg.lora_r, lora_alpha=cfg.lora_alpha, lora_dropout=cfg.lora_dropout,
        bias="none", task_type="CAUSAL_LM", target_modules=targets,
    ))
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log.info("trainable %.1fM / %.1fB (%.3f%%)", trainable/1e6, total/1e9, 100*trainable/total)
    wandb.config.update({"trainable_params": trainable, "total_params": total,
                         "n_lora_targets": len(targets)})

    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=cfg.lr, betas=(cfg.adam_beta1, cfg.adam_beta2),
    )
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 1.0)  # constant LR, as METR

    # --- loop ------------------------------------------------------------
    import random
    order = list(range(len(examples)))
    random.Random(cfg.seed).shuffle(order)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id

    metrics_path = out_root / "train_metrics.jsonl"
    metrics_fh = open(metrics_path, "a", encoding="utf-8")

    model.train()
    step = 0
    micro = 0
    t0 = time.monotonic()
    accum_loss = 0.0
    accum_sup = 0
    accum_tok = 0
    batch_mode_losses: dict[str, list[float]] = {}

    def save_ckpt(step_no: int, metrics: dict):
        d = out_root / (f"step-{step_no}" if step_no < total_steps else "step-final")
        d.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(d)          # adapter only, ~50 MB at r=32
        tok.save_pretrained(d)
        (d / "train_metrics.json").write_text(json.dumps({"step": step_no, **metrics}, indent=2))
        art = wandb.Artifact(f"adapter-step{step_no}", type="lora-adapter", metadata={"step": step_no, **metrics})
        art.add_dir(str(d))
        wandb_run.log_artifact(art)
        log.info("saved %s", d)

    for epoch in range(cfg.epochs):
        for i in order:
            e = examples[i]
            batch = collate([e], pad_id)
            batch = {k: v.to("cuda") for k, v in batch.items()}
            step_loss = chunked_causal_loss(model, batch, chunk=args.loss_chunk)
            (step_loss / cfg.grad_accum).backward()

            accum_loss += step_loss.item()
            batch_mode_losses.setdefault(e.mode, []).append(step_loss.item())
            accum_sup += int((batch["labels"] != IGNORE_INDEX).sum().item())
            accum_tok += int(batch["attention_mask"].sum().item())
            micro += 1

            if micro % cfg.grad_accum:
                continue

            gnorm = torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], cfg.max_grad_norm
            )
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
            step += 1

            if step % cfg.log_every == 0:
                elapsed = time.monotonic() - t0
                lora_norm = math.sqrt(sum(
                    float(p.detach().float().pow(2).sum()) for p in model.parameters() if p.requires_grad
                ))
                # supervised_fraction is the guard rail: loss is assistant-only, so this drifting
                # to ~0 or ~1 means the mask broke and the run is invalid.
                wandb.log({
                    "train/loss": accum_loss / cfg.grad_accum,
                    "train/grad_norm": float(gnorm),
                    "train/lr": sched.get_last_lr()[0],
                    "train/step": step,
                    "tokens/supervised_per_batch": accum_sup,
                    "tokens/total_per_batch": accum_tok,
                    "tokens/supervised_fraction": accum_sup / max(1, accum_tok),
                    "perf/tokens_per_s": accum_tok / max(1e-9, elapsed),
                    "perf/step_seconds": elapsed,
                    "gpu/mem_allocated_gb": torch.cuda.memory_allocated() / 1e9,
                    "gpu/mem_reserved_gb": torch.cuda.memory_reserved() / 1e9,
                    "gpu/max_mem_allocated_gb": torch.cuda.max_memory_allocated() / 1e9,
                    "train/perplexity": math.exp(min(20.0, accum_loss / cfg.grad_accum)),
                    "train/progress": step / total_steps,
                    "lora/param_l2_norm": lora_norm,
                    "seq/len_mean": accum_tok / cfg.grad_accum,
                    "seq/supervised_mean": accum_sup / cfg.grad_accum,
                }, step=step)
                metrics_fh.write(json.dumps({
                    "step": step, "loss": accum_loss / cfg.grad_accum, "grad_norm": float(gnorm),
                    "supervised_fraction": accum_sup / max(1, accum_tok),
                    "lora_l2": lora_norm, "seconds": elapsed,
                }) + "\n")
                metrics_fh.flush()
                # Per-mode loss: if one constraint is far harder to fit, it shows here rather
                # than being averaged away.
                for m, vals in batch_mode_losses.items():
                    wandb.log({f"loss_by_mode/{m}": sum(vals) / len(vals)}, step=step)
                batch_mode_losses.clear()

            if step in ckpt_steps or (cfg.push_every and step % cfg.push_every == 0):
                save_ckpt(step, {"loss": accum_loss / cfg.grad_accum, "grad_norm": float(gnorm)})

            accum_loss = 0.0; accum_sup = 0; accum_tok = 0; t0 = time.monotonic()
            if args.smoke and step >= args.smoke:
                log.info("smoke limit reached at step %d", step)
                wandb_run.finish()
                return 0

    # Always leave a `step-final` adapter: the loop may take fewer optimizer steps than planned
    # (incomplete accumulation groups are dropped), in which case the planned final step is never hit.
    if not (out_root / "step-final" / "adapter_config.json").exists():
        save_ckpt(max(step, total_steps), {"loss": accum_loss / cfg.grad_accum if cfg.grad_accum else None, "actual_steps": step})
    metrics_fh.close()
    wandb_run.finish()
    log.info("done: %d steps; metrics at %s", step, metrics_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
