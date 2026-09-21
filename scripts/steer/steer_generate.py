#!/usr/bin/env python3
"""Piece 5 CLI: steered rollouts.
  python scripts/steer/steer_generate.py --model PATH --directions results/steer/directions_<tag>.pt --layer 16 --pooling mean \
      --coefs -8 0 8 --suite cotcontrol --modes uppercase_thinking no_comma --n 40 --label base --max-new-tokens 8192
Prompts are the stored eval prompts (same questions as every other run), first --n per mode. Output:
results/steer/rollouts_<label>_<suite>_L<layer>_c<coef>.jsonl in the standard rollout schema.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import torch
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.activations import load_model
from cotctl.steer.harness import generate_steered
ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True); ap.add_argument("--directions", required=True); ap.add_argument("--layer", type=int, required=True); ap.add_argument("--pooling", default="mean")
ap.add_argument("--coefs", type=float, nargs="+", default=[-8, 0, 8]); ap.add_argument("--suite", default="cotcontrol"); ap.add_argument("--modes", nargs="+", default=None); ap.add_argument("--n", type=int, default=40)
ap.add_argument("--label", default="base"); ap.add_argument("--max-new-tokens", type=int, default=8192); ap.add_argument("--batch-size", type=int, default=4); ap.add_argument("--device", default="cuda"); ap.add_argument("--dtype", default="bfloat16"); ap.add_argument("--tag", default=None)
a = ap.parse_args(); D = torch.load(a.directions); unit = D["directions"][a.layer][a.pooling]
model, tok = load_model(a.model, dtype=getattr(torch, a.dtype), device=a.device)
rows = [json.loads(l) for l in open(REPO / f"results/{a.label}/{a.suite}_rollouts.jsonl")]
prompts, seen = [], {}
for r in rows:
    if a.modes and r["mode"] not in a.modes: continue
    if seen.get(r["mode"], 0) >= a.n: continue
    prompts.append({"sample_id": r["sample_id"], "mode": r["mode"], "prompt": r["prompt"], "meta": r.get("meta") or {}}); seen[r["mode"]] = seen.get(r["mode"], 0) + 1
tag = a.tag or Path(a.model).name
for c in a.coefs:
    out = REPO / f"results/steer/rollouts_{a.label}_{a.suite}_{tag}_L{a.layer}_{a.pooling}_c{c:+g}.jsonl"
    if out.exists(): out.unlink()
    rs = generate_steered(model, tok, prompts, a.layer, unit, c, max_new_tokens=a.max_new_tokens, batch_size=a.batch_size, model_name=f"{tag}+steer", out_path=out, meta_extra={"direction": Path(a.directions).stem, "pooling": a.pooling})
    ok = sum(r["think_status"] == "ok" for r in rs); print(f"coef {c:+g}: {len(rs)} rollouts, {ok} closed think blocks, mean completion {sum(r['completion_tokens'] for r in rs)/len(rs):.0f} tokens -> {out.name}", flush=True)
