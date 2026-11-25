"""Set the banned-string penalty's scale from a model's first rollouts.

calibrate.py <train_samples.jsonl> <sqrt|linear> <quantile> <reward.env>
cap = the given quantile of the banned-string counts of the monitored completions (at least 1); the penalty reaches
its maximum of 1 at cap strings: linear = min(1, n / cap), sqrt = min(1, sqrt(n / cap)).
"""
import json, sys

path, shape, q, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
if shape not in ("sqrt", "linear"):
    sys.exit(f"unknown shape {shape!r}")
b = sorted(r["banned"] for r in map(json.loads, open(path)) if r["banned"] is not None)
if len(b) < 32:
    sys.exit(f"calibration: only {len(b)} monitored completions in {path}")
at = lambda p: b[min(len(b) - 1, int(p * len(b)))]
cap = max(1, at(q))
open(out, "w").write(f"PENALTY={shape}\nPER_MENTION={1 / cap:.6f}\n")
print(f"calibration: {len(b)} completions, banned strings min {b[0]} median {at(.5)} p90 {at(.9)} p95 {at(.95)} "
      f"max {b[-1]}; {shape} penalty, cap at {cap} (quantile {q}), share above the cap {sum(x > cap for x in b) / len(b):.2f}")
