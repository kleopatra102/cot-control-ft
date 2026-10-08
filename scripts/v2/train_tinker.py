#!/usr/bin/env python3
"""LoRA SFT on Tinker for the unlearning arms (UNLEARNING_V2_PLAN.md, step 3): the same recipe as our local trainers
(LoRA r 32 on attention + MLP, Adam (0.9, 0.95), lr 1e-4, batch 4, one epoch, loss on the assistant turn only).

Rows are {"messages": [developer?, user, assistant]} with the assistant content "<think>\\n{reasoning}\\n</think>\\n\\n{answer}".
They are rendered with the same tinker-cookbook renderer used for sampling, so the reasoning goes into the model's
thinking block exactly as it is sampled. Writes results/unlearn_v2/<key>/ckpt_<name>.json with the sampler path.

  .venv-tinker/bin/python scripts/v2/train_tinker.py --key qwen38_tinker --name U --data data/sft/unlearn_v2_qwen38_tinker_U.jsonl
"""
from __future__ import annotations
import argparse, json, math, random, re, sys, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
import tinker
from tinker_cookbook import renderers
from tinker_cookbook.supervised.common import datum_from_model_input_weights
from unlearn_build import MODELS

THINK_RE = re.compile(r"^<think>\n?(.*?)\n?</think>\s*(.*)$", re.DOTALL)


def to_messages(msgs):
    out = []
    for m in msgs:
        if m["role"] in ("developer", "system"): out.append({"role": "system", "content": m["content"]})
        elif m["role"] == "user": out.append({"role": "user", "content": m["content"]})
        else:
            mm = THINK_RE.match(m["content"]); think, ans = (mm.group(1), mm.group(2).strip()) if mm else ("", m["content"])
            out.append({"role": "assistant", "content": [{"type": "thinking", "thinking": think}, {"type": "text", "text": ans}]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True); ap.add_argument("--name", required=True); ap.add_argument("--data", required=True)
    ap.add_argument("--rank", type=int, default=32); ap.add_argument("--lr", type=float, default=1e-4); ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--max-len", type=int, default=8192); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(); cfg = MODELS[a.key]; out = REPO / "results/unlearn_v2" / a.key; out.mkdir(parents=True, exist_ok=True)
    sc = tinker.ServiceClient()
    tc = sc.create_lora_training_client(base_model=cfg["tinker"], rank=a.rank, seed=a.seed, train_mlp=True, train_attn=True, train_unembed=False)
    rend = renderers.get_renderer(cfg["renderer"], tc.get_tokenizer())
    rows = [json.loads(l) for l in open(REPO / a.data) if l.strip()]
    data, dropped = [], 0
    for r in rows:
        mi, w = rend.build_supervised_example(to_messages(r["messages"]))
        if mi.length > a.max_len: dropped += 1; continue
        data.append(datum_from_model_input_weights(mi, w, a.max_len))
    random.Random(a.seed).shuffle(data)
    if a.limit: data = data[: a.limit]
    steps = math.ceil(len(data) / a.batch)
    print(f"{len(data)} examples ({dropped} over {a.max_len} tokens dropped) -> {steps} steps", flush=True)
    log = open(out / f"train_{a.name}.jsonl", "w"); t0 = time.time(); adam = tinker.AdamParams(learning_rate=a.lr, beta1=0.9, beta2=0.95)
    for s in range(steps):
        batch = data[s * a.batch:(s + 1) * a.batch]
        fb = tc.forward_backward(batch, "cross_entropy"); opt = tc.optim_step(adam)
        res = fb.result(); opt.result()
        m = getattr(res, "metrics", {}) or {}
        ntok = sum(float(d.loss_fn_inputs["weights"].to_torch().sum()) for d in batch)
        loss = m.get("loss:sum", float("nan")) / max(ntok, 1)
        rec = {"step": s + 1, "loss": round(loss, 4), "seconds": round(time.time() - t0, 1)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if (s + 1) % 20 == 0 or s == 0: print(rec, flush=True)
    path = tc.save_weights_for_sampler(name=f"unlearn-v2-{a.key}-{a.name}").result().path
    json.dump({"name": a.name, "base_model": cfg["tinker"], "sampler_path": path, "examples": len(data), "steps": steps, "lr": a.lr,
               "rank": a.rank, "batch": a.batch, "data": a.data}, open(out / f"ckpt_{a.name}.json", "w"), indent=1)
    print("saved", path, flush=True)


if __name__ == "__main__":
    main()
