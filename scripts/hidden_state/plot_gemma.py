#!/usr/bin/env python3
"""Figures for HIDDEN_STATE_GEMMA_FINDINGS.md from the cell logs in results/hidden_state/<task>/<arm>/<condition>.log.
Writes figs/hidden_state/{clean,density}.{svg,png}."""
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]; RES = REPO / "results/hidden_state"; OUT = REPO / "figs/hidden_state"
BASE, TRAINED = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
TASKS = ["coinflip", "direction", "lookup"]; ARMS = [("base", "base", BASE), ("treated", "trained (v2 B)", TRAINED)]
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF})


def summ(task, arm, cond):
    for l in open(RES / task / arm / f"{cond}.log"):
        if l.startswith("summary"): return json.loads(l[8:])


def bars(ax, conds, value, fmt, top):
    w = 0.36
    for i, (arm, _, col) in enumerate(ARMS):
        for j, c in enumerate(conds):
            v = value(arm, c); x = j + (i - 0.5) * w
            ax.bar(x, v, w - 0.04, color=col, edgecolor=SURF, linewidth=2)
            ax.text(x, v + top * 0.015, fmt(v), ha="center", va="bottom", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(conds))); ax.set_ylim(0, top)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"): fig.savefig(OUT / f"{name}.{ext}", dpi=160, facecolor=SURF)
    plt.close(fig)


def legend(fig):
    from matplotlib.patches import Patch
    fig.legend([Patch(color=col) for _, _, col in ARMS], [label for _, label, _ in ARMS], loc="upper right",
               bbox_to_anchor=(0.99, 0.99), frameon=False, fontsize=9.5, ncol=2)


# 1. Clean rate: correct and zero banned words
conds = ["notice", "nonotice", "prefill"]
def matched(a, c):  # lookup re-scored with a monitor matching its notice (scripts/hidden_state/rescore_lookup.py)
    return json.load(open(RES / "lookup" / a / f"{c}.notice_matched.json"))


panels = [(t, t, lambda a, c, t=t: summ(t, a, c)) for t in TASKS[:2]] + [("lookup", "lookup, original monitor (+ numbers)", lambda a, c: summ("lookup", a, c)),
          ("lookup", "lookup, monitor = the notice (X + digit)", matched)]
fig, axs = plt.subplots(1, 4, figsize=(14, 3.9), sharey=True)
for ax, (t, title, get) in zip(axs, panels):
    bars(ax, conds, lambda a, c: 100 * get(a, c)["clean_strict"], lambda v: f"{v:.0f}", 36)
    ax.set_xticklabels(["notice", "no notice", "prefill"]); ax.set_title(title, fontsize=10 if t != title else 11, color=INK, loc="left")
axs[0].set_ylabel("% correct with no banned word")
fig.text(0.01, 0.97, "Trained Gemma avoids the banned words more often, by renaming the state", fontsize=13, fontweight="bold", color=INK, va="top")
fig.text(0.01, 0.905, "Gemma-4-31B base vs v2 B; 160 samples per bar. Hand check: every clean sample renames the state (H/T, Side 1, S7, index 5); none hides it.\nLookup's original monitor also bans bare numbers and number words, which the notice never mentions; the last panel scores only what the notice bans.",
         fontsize=9, color=INK2, va="top")
legend(fig); fig.tight_layout(rect=(0, 0, 1, 0.82)); save(fig, "clean")

# 2. Banned words per 100 reasoning words (density) and reasoning length
fig, axs = plt.subplots(1, 3, figsize=(12, 4.1))
for ax, t in zip(axs, TASKS):
    d = lambda a, c: 100 * summ(t, a, c)["banned"] / summ(t, a, c)["reasoning_words"]
    top = max(d(a, c) for a, _, _ in ARMS for c in conds) * 1.25
    bars(ax, conds, d, lambda v: f"{v:.1f}", top)
    ax.set_xticklabels([f"{lab}\n{summ(t, 'base', c)['reasoning_words']:.0f} / {summ(t, 'treated', c)['reasoning_words']:.0f} w"
                        for lab, c in zip(["notice", "no notice", "prefill"], conds)], fontsize=8.5)
    ax.set_title(t, fontsize=11, color=INK, loc="left")
axs[0].set_ylabel("banned words per 100 reasoning words")
fig.text(0.01, 0.97, "Per word of reasoning, the two models mention the state at similar rates", fontsize=13, fontweight="bold", color=INK, va="top")
fig.text(0.01, 0.905, "The trained model's lower banned-word count comes mostly from shorter reasoning (mean words: base / trained, under each group)",
         fontsize=9, color=INK2, va="top")
legend(fig); fig.tight_layout(rect=(0, 0, 1, 0.85)); save(fig, "density")
print("wrote", sorted(p.name for p in OUT.iterdir()))

# 3. Reasoning length by condition: median and interquartile range of words per sample
import statistics as st


def words(t, a, c):
    return [len((json.loads(l)["reasoning"] or "").split()) for l in open(RES / t / a / c / "samples_reasoning.jsonl")]


lconds = [("nonotice", "no notice"), ("notice", "notice"), ("prefill", "prefill")]
fig, axs = plt.subplots(1, 3, figsize=(12, 4.1), sharey=True)
for ax, t in zip(axs, TASKS):
    w = 0.36
    for i, (arm, _, col) in enumerate(ARMS):
        for j, (c, _) in enumerate(lconds):
            q1, med, q3 = st.quantiles(words(t, arm, c), n=4); x = j + (i - 0.5) * w
            ax.bar(x, med, w - 0.04, color=col, edgecolor=SURF, linewidth=2)
            ax.plot([x, x], [q1, q3], color=INK, lw=1.2, alpha=0.55, solid_capstyle="round")
            ax.text(x, q3 + 18, f"{med:.0f}", ha="center", va="bottom", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(lconds))); ax.set_xticklabels([lab for _, lab in lconds]); ax.set_ylim(0, 1250)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_title(t, fontsize=11, color=INK, loc="left")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
axs[0].set_ylabel("words of reasoning per sample")
fig.text(0.01, 0.97, "The notice makes base's coinflip reasoning 5x longer; elsewhere length changes little",
         fontsize=13, fontweight="bold", color=INK, va="top")
fig.text(0.01, 0.905, "Gemma-4-31B, 6 steps, 160 samples per bar; bar = median, line = middle half of samples (25th to 75th percentile). "
         "Prefill shortens base's reasoning again.", fontsize=9, color=INK2, va="top")
legend(fig); fig.tight_layout(rect=(0, 0, 1, 0.85)); save(fig, "length")
print("wrote length")
