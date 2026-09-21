#!/usr/bin/env python3
"""Piece 1 CLI: python scripts/steer/build_spans.py --label base --suite cotcontrol [--tokenizer PATH]"""
from __future__ import annotations
import argparse, sys, json, statistics as st
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.spans import build_spans, write_spans
ap = argparse.ArgumentParser(); ap.add_argument("--label", default="base"); ap.add_argument("--suite", default="cotcontrol")
ap.add_argument("--tokenizer", default="Qwen/Qwen3.5-9B"); ap.add_argument("--max-per-trace", type=int, default=6); ap.add_argument("--max-tokens", type=int, default=12000)
a = ap.parse_args()
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(a.tokenizer)
spans = build_spans(a.label, a.suite, REPO, tok, max_per_trace=a.max_per_trace, max_tokens=a.max_tokens)
out = REPO / f"results/steer/spans_{a.label}_{a.suite}.jsonl"; write_spans(spans, out)
pos = [s for s in spans if s.is_narration]; neg = [s for s in spans if not s.is_narration]
print(f"{len(pos)} narration + {len(neg)} matched negatives from {len({s.sample_id+s.mode for s in spans})} traces -> {out}")
print("per mode:", dict(Counter(s.mode for s in pos)))
print(f"median tokens/span: narration {st.median(s.tok_end-s.tok_start for s in pos):.0f}, negative {st.median(s.tok_end-s.tok_start for s in neg):.0f}; median |pos_frac gap| {st.median(abs(p.pos_frac-n.pos_frac) for p,n in zip(pos,neg)):.3f}")
