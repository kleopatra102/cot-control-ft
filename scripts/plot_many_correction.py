#!/usr/bin/env python3
"""Before/after of the 2026-10-03 correction: previous numbers (macro over conditions, leaked conditions included)
against corrected ones (macro over operations, leaked held-out conditions removed), three models."""
import importlib.util, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]
SETS = [("qwen38", "Qwen3.8-27B"), ("gptoss", "gpt-oss-20b"), ("r1", "R1-Llama-8B")]
V = {}
for key, name in SETS:
    sys.argv = ["x", f"--set={key}"]; sp = importlib.util.spec_from_file_location(f"r_{key}", REPO / "scripts/report_many_rules.py")
    R = importlib.util.module_from_spec(sp); sp.loader.exec_module(R)
    old = {arm: [c for c in R.EVALUATED if c in R.TEST[arm] and c not in R.Q5_TRAINED and c not in R.BASE_HIGH] for arm in "AB"}
    V[name] = {}
    for arm in "AB":
        V[name][f"own{arm}"] = {"Q5": (R.macro("Q5", old[arm]), R.opmacro("Q5", R.HELD[arm])), arm: (R.macro(arm, old[arm]), R.opmacro(arm, R.HELD[arm]))}
    V[name]["core"] = {m: (R.macro(m, R.CORE), R.opmacro(m, R.CORE)) for m in ("Q5", "A", "B")}
C, SURF, INK, INK2, GRID = R.C, R.SURF, R.INK, R.INK2, R.GRID
NAME = {"Q5": "Q5 (6 rules)", "A": "A (family split)", "B": "B (within-family split)"}
panels = [("ownA", "A on its own held-out set", ["Q5", "A"]), ("ownB", "B on its own held-out set", ["Q5", "B"]), ("core", "Shared core (held out by all)", ["Q5", "A", "B"])]
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharey=True)
for ax, (k, ttl, ms) in zip(axes, panels):
    x = 0; ticks = []
    for _, name in SETS:
        for j, m in enumerate(ms):
            before, after = V[name][k][m]; xb = x + j * 0.9
            ax.bar(xb, before, width=0.42, color=C[m], alpha=0.3, edgecolor=SURF, label=f"{NAME[m]}: previous" if name == SETS[0][1] else None)
            ax.bar(xb + 0.42, after, width=0.42, color=C[m], edgecolor=SURF, label=f"{NAME[m]}: corrected" if name == SETS[0][1] else None)
            ax.text(xb, before + 0.8, f"{before:.0f}", ha="center", fontsize=7, color=INK2); ax.text(xb + 0.42, after + 0.8, f"{after:.0f}", ha="center", fontsize=7.5, color=INK)
        ticks.append((x + (len(ms) - 1) * 0.45 + 0.21, name)); x += len(ms) * 0.9 + 0.8
    ax.set_xticks([t for t, _ in ticks]); ax.set_xticklabels([l for _, l in ticks], fontsize=8.5); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
axes[0].set_ylabel("held-out rules satisfied, %")
from matplotlib.patches import Patch
hs = [Patch(color=C[m], label=NAME[m]) for m in ("Q5", "A", "B")] + [Patch(color="#52514e", alpha=0.3, label="previous"), Patch(color="#52514e", label="corrected")]
fig.legend(handles=hs, frameon=False, fontsize=8.5, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.04))
fig.suptitle("Correction: faded = previous (each condition counted, leaked conditions included); solid = corrected "
             "(each operation counted once, leaked conditions removed)", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0.04, 1, 0.93)); fig.savefig(REPO / "figures/many_correction.png", bbox_inches="tight")
for n in V: print(n, {k: {m: tuple(round(x) for x in v) for m, v in d.items()} for k, d in V[n].items()})
