#!/usr/bin/env python3
"""Many-rule SFT across three models: held-out transfer (shared core; each arm's own held-out set) and accuracy."""
import importlib, json, statistics as st, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "scripts"))
SETS = [("qwen38", "Qwen3.8-27B"), ("gptoss", "gpt-oss-20b"), ("r1", "R1-Distill-Llama-8B")]
D = {}
for key, name in SETS:
    sys.argv = ["x", f"--set={key}"]; R = importlib.reload(importlib.import_module("report_many_rules"))  # values are read inside the loop, so reuse is safe
    acc = {m: 100 * st.mean(bool(json.loads(l)["correct"]) for l in open(R.RWD[m] / "graded.jsonl")) for m in R.MODELS}
    D[name] = {"core": {m: R.opmacro(m, R.CORE) for m in R.MODELS},
               "own": {"base": st.mean([R.opmacro("base", R.HELD["A"]), R.opmacro("base", R.HELD["B"])]), "Q5": st.mean([R.opmacro("Q5", R.HELD["A"]), R.opmacro("Q5", R.HELD["B"])]),
                       "A": R.opmacro("A", R.HELD["A"]), "B": R.opmacro("B", R.HELD["B"])}, "acc": acc}
C, SURF, INK, INK2, MUTED, GRID = R.C, R.SURF, R.INK, R.INK2, R.MUTED, R.GRID
NAME = {"base": "base", "Q5": "Q5 (6 rules)", "A": "A (family split)", "B": "B (within-family split)"}
fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), gridspec_kw={"width_ratios": [1, 1, 1]})
panels = [("core", "Shared core: held out by every model, macro over operations %"), ("own", "Own held-out set, leaks removed, macro over operations %\n(base and Q5: mean of the two sets)"),
          ("acc", "Answer accuracy on Redwood's tasks, %")]
w = 0.2
for ax, (k, ttl) in zip(axes, panels):
    for j, m in enumerate(["base", "Q5", "A", "B"]):
        xs = [i + (j - 1.5) * w for i in range(len(SETS))]; ys = [D[n][k][m] for _, n in SETS]
        ax.bar(xs, ys, width=w * 0.95, color=C[m], edgecolor=SURF, label=NAME[m])
        for x, y in zip(xs, ys): ax.text(x, y + (0.8 if k != "acc" else 1.2), f"{y:.0f}", ha="center", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(SETS))); ax.set_xticklabels([n for _, n in SETS], fontsize=8.5); ax.set_title(ttl, loc="left", fontsize=9.5, color=INK)
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
    if k == "acc": ax.set_ylim(0, 100)
h, l = axes[0].get_legend_handles_labels(); fig.legend(h, l, frameon=False, fontsize=9, loc="upper right", ncol=4, bbox_to_anchor=(1.0, 1.0))
fig.suptitle("Many-rule SFT across three model families", x=0.01, ha="left", fontsize=11.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.92)); fig.savefig(REPO / "figures/many_three_models.png", bbox_inches="tight")
for n in D: print(n, {k: {m: round(v, 1) for m, v in D[n][k].items()} for k in D[n]})
