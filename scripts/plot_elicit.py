#!/usr/bin/env python3
"""Elicitation figures from results/elicit*/summary.json (run `run_elicit.py report` first)."""
import json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
STRATS = [("E0", "plain"), ("E1", "Redwood-style\nwording"), ("E2", "monitor /\nevaluation"), ("E7", "rules ×15"), ("E6", "gpt-5\noptimised"), ("E4", "best of 3"), ("E5", "prefill"), ("E31", "worked\nexample")]
def draw(sub, models, colors, fname, title):
    rows = json.load(open(REPO / f"results/{sub}/summary.json")); get = {(r["model"], r["strategy"]): r for r in rows if r["level"] == "all"}
    fig, axes = plt.subplots(1, 2, figsize=(15, 4.6), gridspec_kw={"width_ratios": [3, 2]})
    w = 0.8 / len(models); ax = axes[0]
    for j, m in enumerate(models):
        ys = [100 * get[(m, s)]["joint"] if (m, s) in get else 0 for s, _ in STRATS]
        ax.bar([i + (j - (len(models) - 1) / 2) * w for i in range(len(STRATS))], ys, width=w, color=colors[m], edgecolor=SURF, label=m)
        for i, y in enumerate(ys): ax.text(i + (j - (len(models) - 1) / 2) * w, y + 0.8, f"{y:.0f}", ha="center", fontsize=7, color=INK2)
    ax.set_xticks(range(len(STRATS))); ax.set_xticklabels([n for _, n in STRATS], fontsize=8.5); ax.set_ylabel("all constraints met, %"); style(ax)
    ax.legend(frameon=False, fontsize=9, loc="upper left"); ax.set_title("compliance by strategy (160 test prompts each)", loc="left", fontsize=10, color=INK)
    ax = axes[1]
    for m in models:
        base_acc = get[(m, "E0")]["accuracy"]
        for s, n in STRATS:
            if (m, s) not in get: continue
            r = get[(m, s)]; x = 100 * (r["accuracy"] - base_acc); y = 100 * r["joint"]
            ax.scatter([x], [y], color=colors[m], s=46, edgecolor=SURF, zorder=3, label=m if s == "E0" else None)
            if s in ("E5", "E31", "E4", "E6"): ax.annotate(n.replace("\n", " "), (x, y), fontsize=7, color=MUTED, xytext=(4, 3), textcoords="offset points")
    ax.axvline(-10, color=MUTED, ls=":", lw=1); ax.text(-10.5, ax.get_ylim()[1] * 0.97, "admissibility\nlimit (−10 pts)", ha="right", va="top", fontsize=7.5, color=MUTED)
    ax.set_xlabel("accuracy change vs the same model's plain prompt, points"); ax.set_ylabel("all constraints met, %"); style(ax)
    ax.set_title("compliance against accuracy cost (wording strategies unlabelled, they cluster at each model's plain point)", loc="left", fontsize=9.5, color=INK)
    ax.legend(frameon=False, fontsize=8.5, loc="center right")
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK); fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/{fname}.png", bbox_inches="tight"); plt.close(fig)
    print("wrote", fname)
if "--gptoss" in sys.argv:
    draw("elicit_gptoss", ["base", "T3"], {"base": "#c3c2b7", "T3": "#104281"}, "elicit_gptoss", "gpt-oss-20b: the same elicitation strategies on base and the fine-tuned T3")
else:
    draw("elicit", ["base", "Q5", "U"], {"base": "#c3c2b7", "Q5": "#eb6834", "U": "#7d7a6f"}, "elicit_qwen3_8b", "Qwen3-8B: the same elicitation strategies on base, the fine-tuned Q5, and the unlearned U")
