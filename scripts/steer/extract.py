#!/usr/bin/env python3
"""Piece 3 CLI: activations for spans and quartets.
  python scripts/steer/extract.py --model Qwen/Qwen3.5-9B --label base --suite cotcontrol --layers 8 12 16 20 24 [--limit N]
Writes results/steer/acts_<label>_<suite>_<tag>.pt with span vectors (mean & last, all requested layers) + metadata,
and, with --pairs, results/steer/pairacts_<label>_<tag>.pt with per-text vectors for A/B/C/D.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import torch
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.activations import load_model, span_vectors, text_vector, token_range
from cotctl.steer.spans import full_text
ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--tag", default=None); ap.add_argument("--label", default="base"); ap.add_argument("--suite", default="cotcontrol")
ap.add_argument("--layers", type=int, nargs="+", default=[8, 12, 16, 20, 24]); ap.add_argument("--limit", type=int, default=None); ap.add_argument("--device", default="cuda")
ap.add_argument("--dtype", default="bfloat16"); ap.add_argument("--pairs", action="store_true"); ap.add_argument("--spans-file", default=None); ap.add_argument("--pairs-file", default=None)
ap.add_argument("--stratify", action="store_true", help="round-robin across modes so --limit covers every mode"); ap.add_argument("--exclude-modes", nargs="*", default=[])
a = ap.parse_args(); tag = a.tag or Path(a.model).name
dtype = getattr(torch, a.dtype); model, tok = load_model(a.model, dtype=dtype, device=a.device)
OUT = REPO / "results/steer"; OUT.mkdir(parents=True, exist_ok=True)
if not a.pairs:
    spans = [json.loads(l) for l in open(a.spans_file or OUT / f"spans_{a.label}_{a.suite}.jsonl")]
    by = {}
    for s in spans: by.setdefault((s["sample_id"], s["mode"]), []).append(s)
    rollouts = {(r["sample_id"], r["mode"]): r for r in map(json.loads, open(REPO / f"results/{a.label}/{a.suite}_rollouts.jsonl"))}
    keys = [k for k in by if k[1] not in set(a.exclude_modes)]
    if a.stratify:
        import itertools
        per = {}
        for k in keys: per.setdefault(k[1], []).append(k)
        keys = [k for k in itertools.chain.from_iterable(itertools.zip_longest(*per.values())) if k is not None]
    keys = keys[: a.limit] if a.limit else keys
    mean, last, meta = [], [], []; t0 = time.time()
    for i, k in enumerate(keys):
        r = rollouts[k]; text, off = full_text(tok, r["prompt"], r["reasoning"], r.get("answer") or "")
        ss = by[k]; ranges = [token_range(tok, text, off + s["char_start"], s["char_len"]) for s in ss]
        v = span_vectors(model, tok, text, ranges, a.layers, device=a.device)
        mean.append(v["mean"]); last.append(v["last"]); meta.extend({kk: s[kk] for kk in ("label", "suite", "sample_id", "mode", "unit_idx", "is_narration", "pos_frac", "partner_idx")} for s in ss)
        if (i + 1) % 25 == 0: print(f"{i+1}/{len(keys)} traces, {time.time()-t0:.0f}s", flush=True)
    torch.save({"layers": a.layers, "mean": torch.cat(mean), "last": torch.cat(last), "meta": meta}, OUT / f"acts_{a.label}_{a.suite}_{tag}.pt")
    print(f"saved {len(meta)} span vectors x {len(a.layers)} layers -> acts_{a.label}_{a.suite}_{tag}.pt ({time.time()-t0:.0f}s)")
else:
    quart = [json.loads(l) for l in open(a.pairs_file or OUT / f"pairs_{a.label}.jsonl")]
    if a.limit: quart = quart[: a.limit]
    vecs = {k: [] for k in "ABCD"}; meta = []; t0 = time.time()
    for i, q in enumerate(quart):
        for k, (pr, tr) in zip("ABCD", ((q["prompt_instr"], q["trace_orig"]), (q["prompt_instr"], q["trace_compliant"]), (q["prompt_plain"], q["trace_orig"]), (q["prompt_plain"], q["trace_compliant"]))):
            text, off = full_text(tok, pr, tr); a_, b_ = token_range(tok, text, off, len(tr))
            vecs[k].append(text_vector(model, tok, text, a.layers, span=(a_, b_), device=a.device))
        meta.append({kk: q[kk] for kk in ("label", "suite", "mode", "sample_id")})
        if (i + 1) % 10 == 0: print(f"{i+1}/{len(quart)} quartets, {time.time()-t0:.0f}s", flush=True)
    torch.save({"layers": a.layers, **{k: torch.stack(v) for k, v in vecs.items()}, "meta": meta}, OUT / f"pairacts_{a.label}_{tag}.pt")
    print(f"saved {len(meta)} quartets x 4 texts x {len(a.layers)} layers -> pairacts_{a.label}_{tag}.pt ({time.time()-t0:.0f}s)")
