#!/usr/bin/env python3
"""Pre-registered rule split for the unlearning experiment (UNLEARNING_V2_PLAN.md, "Rule split").

Unit: the 20 operations of the v2 rule set (2 rules each; both rules of an operation go to the same side).
Matched-pair randomisation per model: rank the operations by the model's own base controllability (best of 3 above
chance, mean of the operation's two rules, from screening), pair neighbours (1-2, 3-4, ...), and within each pair send
one operation to the unlearned half and the other to the held-out half by a seeded coin flip.
Ties are broken by family and operation name, so the ranking is deterministic.

    python scripts/v2/make_unlearn_split.py gemma4 qwen38_tinker
Writes data/unlearn_v2_splits.json and prints a markdown table per model.
"""
import json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import C

SEED = "unlearn-v2-split:{model}"
ops = defaultdict(list)
for c in C: ops[(c[0], c[1])].append(c[2])
out_path = REPO / "data/unlearn_v2_splits.json"
out = json.load(open(out_path)) if out_path.exists() else {}
for model in sys.argv[1:]:
    R = json.load(open(REPO / f"results/screen_v2/{model}/summary.json"))["rules"]
    score = {o: st.mean(max(0.0, R[c]["best_of_k"] - R[c]["chance"]) for c in cs) for o, cs in ops.items()}
    order = sorted(ops, key=lambda o: (-round(score[o], 6), o[0], o[1]))
    rng = random.Random(SEED.format(model=model)); unlearn, held = [], []
    for i in range(0, len(order), 2):
        a, b = order[i], order[i + 1]
        if rng.random() < 0.5: a, b = b, a
        unlearn.append(a); held.append(b)
    fam_unlearned = {o[0] for o in unlearn}
    rec = {"seed": SEED.format(model=model), "source": f"results/screen_v2/{model}/summary.json",
           "unlearn": [{"family": o[0], "operation": o[1], "rules": ops[o], "score": round(score[o], 1)} for o in unlearn],
           "held_out": [{"family": o[0], "operation": o[1], "rules": ops[o], "score": round(score[o], 1),
                         "sibling_unlearned": o[0] in fam_unlearned} for o in held]}
    out[model] = rec
    print(f"\n### {model}  (seed '{rec['seed']}')\n")
    print("| pair | unlearned operation (family) | score | held-out operation (family) | score | held-out sibling unlearned? |")
    print("|---|---|---:|---|---:|---|")
    for k, (u, h) in enumerate(zip(rec["unlearn"], rec["held_out"]), 1):
        print(f"| {k} | {u['operation']} ({u['family']}) | {u['score']:.0f} | {h['operation']} ({h['family']}) | {h['score']:.0f} | "
              f"{'yes (near)' if h['sibling_unlearned'] else 'no (far)'} |")
    m = lambda L: st.mean(x["score"] for x in L)
    print(f"\nmean score: unlearned {m(rec['unlearn']):.1f}, held out {m(rec['held_out']):.1f}; "
          f"held-out operations with an unlearned sibling: {sum(h['sibling_unlearned'] for h in rec['held_out'])} of 10")
json.dump(out, open(out_path, "w"), indent=1)
print(f"\nwrote {out_path.relative_to(REPO)}")
