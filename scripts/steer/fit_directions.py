#!/usr/bin/env python3
"""Piece 4 CLI: fit mean-difference directions per layer and run the held-out probe checks.
  python scripts/steer/fit_directions.py --acts results/steer/acts_base_cotcontrol_<tag>.pt [--transfer results/steer/acts_base_reasonif_<tag>.pt]
Splits: (a) held-out questions (20 % of sample_ids), (b) held-out modes (leave-one-mode-out, reported as mean), (c) transfer to a second file.
Saves results/steer/directions_<tag>.pt {layer: {pooling: unit}} and prints the table that picks the layer.
"""
from __future__ import annotations
import argparse, json, random, sys, statistics as st
from pathlib import Path
import torch
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.directions import mean_diff, evaluate, logistic_probe
ap = argparse.ArgumentParser(); ap.add_argument("--acts", required=True); ap.add_argument("--transfer", default=None); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--probe", action="store_true", help="also fit the logistic ceiling (slower)")
a = ap.parse_args(); D = torch.load(a.acts); layers = D["layers"]; y = torch.tensor([m["is_narration"] for m in D["meta"]]); ids = [m["sample_id"] for m in D["meta"]]; modes = [m["mode"] for m in D["meta"]]
rng = random.Random(a.seed); uniq = sorted(set(ids)); test_ids = set(rng.sample(uniq, max(1, len(uniq) // 5)))
is_test = torch.tensor([i in test_ids for i in ids])
T = torch.load(a.transfer) if a.transfer else None
rows = []; directions = {}
for li, L in enumerate(layers):
    directions[L] = {}
    for pooling in ("mean", "last"):
        X = D[pooling][:, li]; _, unit = mean_diff(X[~is_test & y], X[~is_test & ~y]); directions[L][pooling] = unit
        probe = logistic_probe(X[~is_test], y[~is_test]) if a.probe else None
        r = evaluate(unit, X[is_test], y[is_test], probe); row = {"layer": L, "pooling": pooling, "heldout_q_auroc": r["auroc_direction"], "random": r["auroc_random"], "probe": r.get("auroc_probe")}
        # leave-one-mode-out
        lomo = []
        for m in sorted(set(modes)):
            tr = torch.tensor([x != m for x in modes]); te = ~tr
            if int((te & y).sum()) < 5 or int((te & ~y).sum()) < 5: continue
            _, u = mean_diff(X[tr & y], X[tr & ~y]); lomo.append(evaluate(u, X[te], y[te])["auroc_direction"])
        row["heldout_mode_auroc"] = st.mean(lomo) if lomo else None
        if T is not None:
            Xt = T[pooling][:, T["layers"].index(L)] if L in T["layers"] else None
            if Xt is not None: row["transfer_auroc"] = evaluate(unit, Xt, torch.tensor([m["is_narration"] for m in T["meta"]]))["auroc_direction"]
        row["direction_norm"] = float((X[~is_test & y].mean(0) - X[~is_test & ~y].mean(0)).norm()); row["act_norm"] = float(X.norm(dim=1).mean())
        rows.append(row)
tag = Path(a.acts).stem.replace("acts_", "")
torch.save({"layers": layers, "directions": directions, "table": rows}, REPO / f"results/steer/directions_{tag}.pt")
print(f"{'layer':>5} {'pool':>5} {'heldout-Q':>10} {'heldout-mode':>13} {'transfer':>9} {'random':>7} {'probe':>6} {'|v|/|act|':>10}")
for r in rows:
    f = lambda v: "   —" if v is None else f"{v:.3f}"
    print(f"{r['layer']:>5} {r['pooling']:>5} {f(r['heldout_q_auroc']):>10} {f(r['heldout_mode_auroc']):>13} {f(r.get('transfer_auroc')):>9} {f(r['random']):>7} {f(r['probe']):>6} {r['direction_norm']/r['act_norm']:>10.3f}")
json.dump(rows, open(REPO / f"results/steer/directions_{tag}.json", "w"), indent=1); print(f"saved directions_{tag}.pt/.json")
