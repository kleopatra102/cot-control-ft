#!/usr/bin/env python3
"""Per-family stratified faithfulness difference (trained - base) with bootstrap CIs, strict (mentions and relies) and
mentions-only, plus the inverse-variance pooled estimate and heterogeneity Q. Writes results/faith/metrics_both.json."""
import json, math, random
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; F = REPO / "results/faith"
H = ("sycophancy", "consistency", "visual_pattern", "metadata", "grader_hacking", "unethical_info")
PAIRS = (("qwen_base", "qwen_B"), ("gptoss_base", "gptoss_ft"), ("gemma_base", "gemma_B"), ("kimi_base", "kimi_ft"))
def X(l, metric):
    U = [r for r in map(json.loads, open(F / l / "graded.jsonl")) if r.get("uses_hint") and r.get("judge")]
    f = (lambda r: int(r["judge"]["mentions"] and r["judge"]["relies"])) if metric == "strict" else (lambda r: int(r["judge"]["mentions"]))
    return {h: [f(r) for r in U if r["cond"] == h] for h in H}, sum(1 for r in map(json.loads, open(F / l / "graded.jsonl")) if r["cond"] == "none")
def strat(A, B):
    num = den = 0
    for h in H:
        if A[h] and B[h]: w = len(A[h]) * len(B[h]) / (len(A[h]) + len(B[h])); num += w * (sum(B[h]) / len(B[h]) - sum(A[h]) / len(A[h])); den += w
    return num / den
out = {}
for metric in ("strict", "mentions"):
    E = []
    for b, t in PAIRS:
        (A, qa), (B, qb) = X(b, metric), X(t, metric); rng = random.Random(0)
        bs = sorted(strat({h: [rng.choice(v) for _ in v] for h, v in A.items()}, {h: [rng.choice(v) for _ in v] for h, v in B.items()}) for _ in range(4000))
        d = strat(A, B); E.append((d, (bs[3900] - bs[100]) / 3.92))
        pa = sum(map(sum, A.values())) / sum(map(len, A.values())); pb = sum(map(sum, B.values())) / sum(map(len, B.values()))
        out.setdefault(metric, {})[t] = dict(questions=qb, pooled=[round(100 * pa, 1), round(100 * pb, 1)], diff=round(100 * d, 1), ci=[round(100 * bs[100], 1), round(100 * bs[3900], 1)])
    w = [1 / s ** 2 for _, s in E]; m = sum(d * x for (d, _), x in zip(E, w)) / sum(w); se = 1 / math.sqrt(sum(w)); Q = sum(x * (d - m) ** 2 for (d, _), x in zip(E, w))
    out[metric]["pooled_families"] = dict(diff=round(100 * m, 1), ci=[round(100 * (m - 1.96 * se), 1), round(100 * (m + 1.96 * se), 1)], z=round(m / se, 1), Q=round(Q, 1))
(F / "metrics_both.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
