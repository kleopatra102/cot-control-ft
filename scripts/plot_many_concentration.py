#!/usr/bin/env python3
"""Is held-out transfer concentrated in a few conditions or spread evenly? Per-condition heatmap across three models,
and sorted per-condition gains (arm on its own held-out set, minus base)."""
import importlib.util, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "scripts"))
SETS = [("qwen38", "Qwen3.8-27B"), ("gptoss", "gpt-oss-20b"), ("r1", "R1-Llama-8B")]
MODS = {}
for key, name in SETS:
    sys.argv = ["x", f"--set={key}"]  # a separate module instance per model (reload would share one object)
    spec = importlib.util.spec_from_file_location(f"rmr_{key}", REPO / "scripts/report_many_rules.py"); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); MODS[name] = mod
R = MODS[SETS[0][1]]; P = R.P
SURF, INK, INK2, MUTED, GRID = R.SURF, R.INK, R.INK2, R.MUTED, R.GRID
# rows: every condition held out by A or B (registry), evaluated on all three models, never trained by Q5
held_any = set(P.split("A")[1]) | set(P.split("B")[1])
rows = [c for c in R.EVALUATED if c in held_any and c not in R.Q5_TRAINED and all(c in M.EVALUATED for M in MODS.values())]
fam = ["case", "bans", "inclusion", "position", "layout", "structure", "style", "statistics"]
rows.sort(key=lambda c: (fam.index(P.CONDS[c].family), c))
cols = [(n, m) for _, n in SETS for m in ("base", "Q5", "A", "B")]
cmap = LinearSegmentedColormap.from_list("seq", ["#f4f3ee", "#a9c2e3", "#2f6db5", "#173a66"])
fig, ax = plt.subplots(figsize=(11, 0.34 * len(rows) + 2))
for i, c in enumerate(rows):
    for j, (n, m) in enumerate(cols):
        M = MODS[n]; trained = m in "AB" and c in M.TRAIN[m]
        if trained:
            ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor=SURF, edgecolor=GRID, hatch="////", lw=0)); ax.text(j, i, "trained", ha="center", va="center", fontsize=5.5, color=MUTED); continue
        v = M.rate(m, c); ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor=cmap(v / 100), edgecolor=SURF, lw=1.5))
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="white" if v > 55 else INK)
for k in (4, 8): ax.axvline(k - .5, color=INK2, lw=1.2)
ax.set_xlim(-.5, len(cols) - .5); ax.set_ylim(len(rows) - .5, -.5)
ax.set_xticks(range(len(cols))); ax.set_xticklabels([m for _, m in cols], fontsize=8)
for k, (_, n) in enumerate(SETS): ax.text(4 * k + 1.5, -0.9, n, ha="center", fontsize=9.5, color=INK)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([f"{c.split(':', 1)[1].replace('_', ' ')} ({P.CONDS[c].family})" for c in rows], fontsize=7.5)
ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
ax.set_title("Held-out conditions, % of prompts satisfying the rule (hatched: that arm trained it)", loc="left", fontsize=10, color=INK, pad=34)
fig.tight_layout(); fig.savefig(REPO / "figures/many_heatmap_heldout.png", bbox_inches="tight"); plt.close(fig)

# sorted gains: each arm on its own held-out set (base-high excluded), gain over base, one panel per model x arm
fig, axes = plt.subplots(2, 3, figsize=(15, 6.4), sharey=True)
for col, (_, n) in enumerate(SETS):
    M = MODS[n]
    for row, arm in enumerate("AB"):
        ax = axes[row][col]; g = sorted(((M.rate(arm, c) - M.rate("base", c)), c) for c in M.HELD[arm])[::-1]
        ys = [x for x, _ in g]; ax.bar(range(len(g)), ys, color=M.C[arm], edgecolor=SURF, width=0.8)
        for i, (x, c) in enumerate(g):
            if i < 4: ax.text(i, x + 1.5, c.split(":", 1)[1].replace("_", " ")[:14], rotation=90, ha="center", va="bottom", fontsize=6.5, color=INK2)
        pos = sum(max(0, x) for x in ys); top3 = sum(max(0, x) for x in ys[:3])
        ax.text(0.98, 0.95, f"{sum(x >= 20 for x in ys)} of {len(ys)} conditions gain ≥ 20 points\n{sum(x <= 5 for x in ys)} gain ≤ 5 points\ntop 3 = {100 * top3 / max(pos, 1):.0f} % of total gain",
                transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=INK2)
        ax.axhline(0, color=GRID, lw=1); ax.set_xticks([]); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
        ax.set_ylim(-35, 125)
        if row == 0: ax.set_title(n, loc="left", fontsize=10, color=INK)
        if col == 0: ax.set_ylabel(f"arm {arm}: gain over base,\npercentage points")
fig.suptitle("Held-out gains per condition, sorted (each arm on its own held-out set): a few conditions carry most of the transfer",
             x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(REPO / "figures/many_gain_concentration.png", bbox_inches="tight")
