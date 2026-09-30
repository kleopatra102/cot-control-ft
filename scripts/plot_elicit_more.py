#!/usr/bin/env python3
"""Extra elicitation figures (Qwen3-8B, or gpt-oss with --gptoss): effective control and graded score; single rule vs
triples; per-constraint heatmap by model and strategy."""
import collections, json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
GPT = "--gptoss" in sys.argv
if GPT:
    import os; os.environ["ELICIT_FAMILY"] = "gptoss"; os.environ["COTCTL_NO_ANSWER_TAG"] = "1"
from cotctl import elicit as E
from cotctl.inference import RolloutStore
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
SUB, MODELS, COL, TAG = (("elicit_gptoss", ["base", "T3"], {"base": "#c3c2b7", "T3": "#104281"}, "gptoss") if GPT else
                         ("elicit", ["base", "Q5", "U"], {"base": "#c3c2b7", "Q5": "#eb6834", "U": "#7d7a6f"}, "qwen3_8b"))
STRATS = [("E0", "plain"), ("E1", "Redwood\nwording"), ("E2", "monitor /\nevaluation"), ("E7", "rules ×15"), ("E6", "gpt-5\noptimised"), ("E4", "best of 3"), ("E5", "prefill"), ("E31", "worked\nexample")]
CONS = ["reasoning_language", "number_words", "capital", "end_checker", "no_comma", "end_of_sentence"]
G = {}
for m in MODELS:
    rows = [r for r in RolloutStore(REPO / f"results/{SUB}/{m}/rollouts.jsonl").read_all() if "dev" not in r["mode"].split(":")[0]]
    by = collections.defaultdict(list)
    for r in rows: by[r["meta"]["strategy"]].append(E.grade(r))
    grp = collections.defaultdict(list)
    for g in by.get("E0", []): grp[(g["sample_id"], g["mode"].rsplit("#", 1)[0])].append(g)
    by["E4"] = [max(v, key=lambda x: (bool(x["joint"]), x["continuous"] or 0)) for v in grp.values()]
    G[m] = {s: [g for g in xs if s == "E4" or g["sample"] == 0] for s, xs in by.items()}
def pct(xs, f): return 100 * sum(f(x) for x in xs) / max(1, len(xs))

# 1. effective control and graded score
fig, axes = plt.subplots(1, 2, figsize=(15, 4.3), sharex=True); w = 0.8 / len(MODELS)
for ax, (ttl, f, ylab) in zip(axes, (("effective control: all met, correct answer, no narration, not truncated", lambda xs: pct(xs, lambda x: x["effective"]), "%"),
                                     ("graded score (partial credit), mean over prompts", lambda xs: sum(x["continuous"] or 0 for x in xs) / max(1, len(xs)), "0–1"))):
    for j, m in enumerate(MODELS):
        ys = [f(G[m].get(s, [])) for s, _ in STRATS]
        ax.bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(STRATS))], ys, width=w, color=COL[m], edgecolor=SURF, label=m)
    ax.set_xticks(range(len(STRATS))); ax.set_xticklabels([n for _, n in STRATS], fontsize=8); ax.set_ylabel(ylab); style(ax); ax.set_title(ttl, loc="left", fontsize=9.5, color=INK)
axes[0].legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig(REPO / f"figures/elicit_{TAG}_effective_graded.png", bbox_inches="tight"); plt.close(fig)

# 2. single rule vs triples
fig, axes = plt.subplots(1, 2, figsize=(15, 4.3), sharey=True)
for ax, lvl, ttl in ((axes[0], 1, "single-rule prompts (120)"), (axes[1], 3, "three-rule prompts (40)")):
    for j, m in enumerate(MODELS):
        ys = [pct([x for x in G[m].get(s, []) if x["level"] == lvl], lambda x: bool(x["joint"])) for s, _ in STRATS]
        ax.bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(STRATS))], ys, width=w, color=COL[m], edgecolor=SURF, label=m)
        for i, y in enumerate(ys): ax.text(i + (j - (len(MODELS) - 1) / 2) * w, y + 0.8, f"{y:.0f}", ha="center", fontsize=6.5, color=INK2)
    ax.set_xticks(range(len(STRATS))); ax.set_xticklabels([n for _, n in STRATS], fontsize=8); style(ax); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
axes[0].set_ylabel("all constraints met, %"); axes[0].legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig(REPO / f"figures/elicit_{TAG}_single_vs_triples.png", bbox_inches="tight"); plt.close(fig)

# 3. per-constraint heatmap (single-rule prompts, 20 each)
fig, axes = plt.subplots(1, len(MODELS), figsize=(5.2 * len(MODELS), 4.2), sharey=True)
for ax, m in zip(np.atleast_1d(axes), MODELS):
    M = np.array([[pct([x for x in G[m].get(s, []) if x["constraints"] == [c]], lambda x: bool(x["per_binary"].get(c))) for c in CONS] for s, _ in STRATS])
    ax.imshow(M, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    for i in range(M.shape[0]):
        for k in range(M.shape[1]): ax.text(k, i, f"{M[i,k]:.0f}", ha="center", va="center", fontsize=8, color="white" if M[i, k] > 55 else INK2)
    ax.set_xticks(range(len(CONS))); ax.set_xticklabels(["language", "word\nbudget", "capitals", "end\nphrase", "no\ncomma", "end-of-\nsentence"], fontsize=8)
    ax.set_yticks(range(len(STRATS))); ax.set_yticklabels([n.replace("\n", " ") for _, n in STRATS], fontsize=8.5); ax.tick_params(length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_title(m, loc="left", fontsize=10.5, color=INK)
fig.suptitle("each constraint alone, % satisfied (20 prompts per cell)", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/elicit_{TAG}_per_constraint.png", bbox_inches="tight"); plt.close(fig)
print("wrote 3 figures for", TAG)
