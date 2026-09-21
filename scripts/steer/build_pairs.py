#!/usr/bin/env python3
"""Piece 2 CLI: python scripts/steer/build_pairs.py --label base [--per-mode 200]"""
from __future__ import annotations
import argparse, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.pairs import build_pairs, write_pairs
ap = argparse.ArgumentParser(); ap.add_argument("--label", default="base"); ap.add_argument("--per-mode", type=int, default=200); a = ap.parse_args()
q = build_pairs(a.label, "cotcontrol", REPO, per_mode=a.per_mode) + build_pairs(a.label, "reasonif", REPO, per_mode=a.per_mode)
out = REPO / f"results/steer/pairs_{a.label}.jsonl"; write_pairs(q, out)
print(f"{len(q)} quartets -> {out}; per condition:", dict(Counter((x.suite, x.mode) for x in q)))
