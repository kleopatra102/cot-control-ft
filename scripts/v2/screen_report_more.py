#!/usr/bin/env python3
"""More screening figures (SCREENING_V2_FINDINGS.md):

figures/screen_v2_restating.png  above chance with all traces vs only traces that do not restate the rule, and how often
                                 each model restates it
figures/screen_v2_halves.png     best of 3 above chance in the half each split would unlearn vs the half it holds out
figures/screen_v2_families.png   best of 3 above chance per family, every model (where each model's control lives)
"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import C, role

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, LIGHT, ORANGE = "#2f6db5", "#a9c2e3", "#d9733f"
NAMES = {"gemma4": "Gemma-4-31B", "qwen38_tinker": "Qwen3.8-27B", "deepseek_v31": "DeepSeek-V3.1", "qwen3_32b": "Qwen3-32B",
         "gptoss120b": "gpt-oss-120b", "nemotron3_nano": "Nemotron-3-Nano"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 9.5, "savefig.dpi": 150, "savefig.facecolor": SURF})
OP = {c[2]: (c[0], c[1]) for c in C}; FAMS = list(dict.fromkeys(c[0] for c in C))


def macro(d):
    ops = defaultdict(list)
    for c, v in d.items(): ops[OP[c]].append(v)
    return st.mean(st.mean(v) for v in ops.values()) if ops else 0.0


def style(ax):
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


M = [m for m in NAMES if (REPO / f"results/screen_v2/{m}/summary.json").exists()]
S = {m: json.load(open(REPO / f"results/screen_v2/{m}/summary.json")) for m in M}
G = {m: [json.loads(l) for l in open(REPO / f"results/screen_v2/{m}/graded.jsonl")] for m in M}
above = lambda m, key, cids: macro({c: max(0.0, S[m]["rules"][c][key] - S[m]["rules"][c]["chance"]) for c in cids})

# 1. restating
fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [2.2, 1]})
x = range(len(M)); w = 0.38; allv, nrv = [], []
for m in M:
    nr = defaultdict(list)
    for g in G[m]:
        if g["k"] == 0 and g["ok"] and not g["restates"]: nr[g["cid"]].append(bool(g["compliant"]))
    allv.append(S[m]["macro_plain_above_chance"])
    nrv.append(macro({c: max(0.0, 100 * st.mean(v) - S[m]["rules"][c]["chance"]) for c, v in nr.items() if len(v) >= 5}))
for off, ys, col, lab in ((-w / 2, allv, LIGHT, "all traces"), (w / 2, nrv, BLUE, "only traces that do not restate the rule")):
    a1.bar([i + off for i in x], ys, width=w * 0.94, color=col, edgecolor=SURF, label=lab)
    for i, y in zip(x, ys): a1.text(i + off, y + 0.4, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
a1.set_xticks(list(x)); a1.set_xticklabels([NAMES[m] for m in M], fontsize=8.5, color=INK2); style(a1)
a1.set_ylabel("rules satisfied above chance, % (one sample)", color=INK2); a1.legend(frameon=False, fontsize=8.5, loc="upper right")
a1.set_title("Controllability with and without traces that restate the rule", loc="left", fontsize=10, color=INK)
ys = [S[m]["restates"] for m in M]
a2.barh(list(x), ys, color=ORANGE, edgecolor=SURF, height=0.6)
for i, y in zip(x, ys): a2.text(y + 1, i, f"{y:.0f} %", va="center", fontsize=8.5, color=INK2)
a2.set_yticks(list(x)); a2.set_yticklabels([NAMES[m] for m in M], fontsize=8.5, color=INK2); a2.invert_yaxis(); a2.set_xlim(0, 105)
a2.xaxis.grid(True, color=GRID); a2.set_axisbelow(True); a2.tick_params(length=0, colors=MUTED)
for s in ("top", "right", "left"): a2.spines[s].set_visible(False)
a2.set_title("Traces that restate the rule", loc="left", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/screen_v2_restating.png", bbox_inches="tight"); plt.close(fig)

# 2. halves of each split
fig, axes = plt.subplots(1, 2, figsize=(13, 4.0), sharey=True)
for ax, (sp, lab) in zip(axes, (("A", "by-family split"), ("B", "within-family split"))):
    tr = [c[2] for c in C if role(c, sp) == "train"]; te = [c[2] for c in C if role(c, sp) == "test"]
    for off, cids, col, l in ((-w / 2, tr, LIGHT, "half that would be unlearned"), (w / 2, te, BLUE, "half held out (tests whether unlearning spreads)")):
        ys = [above(m, "best_of_k", cids) for m in M]
        ax.bar([i + off for i in x], ys, width=w * 0.94, color=col, edgecolor=SURF, label=l)
        for i, y in zip(x, ys): ax.text(i + off, y + 0.4, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(list(x)); ax.set_xticklabels([NAMES[m] for m in M], fontsize=8, color=INK2, rotation=15); style(ax)
    ax.set_title(lab, loc="left", fontsize=10, color=INK); ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
axes[0].set_ylabel("best of 3, above chance, %", color=INK2)
fig.suptitle("Where each model's controllability sits: both halves need some, or unlearning cannot be measured on held-out rules",
             x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / "figures/screen_v2_halves.png", bbox_inches="tight"); plt.close(fig)

# 3. family x model
cmap = LinearSegmentedColormap.from_list("seq", ["#f4f3ee", "#a9c2e3", "#2f6db5", "#173a66"])
fig, ax = plt.subplots(figsize=(1.35 * len(M) + 3.2, 0.42 * len(FAMS) + 1.4))
for j, m in enumerate(M):
    for i, f in enumerate(FAMS):
        v = above(m, "best_of_k", [c[2] for c in C if c[0] == f])
        ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor=cmap(min(v, 60) / 60), edgecolor=SURF, lw=1))
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8.5, color="white" if v > 35 else INK)
ax.set_xlim(-.5, len(M) - .5); ax.set_ylim(len(FAMS) - .5, -.5)
ax.set_xticks(range(len(M))); ax.set_xticklabels([NAMES[m] for m in M], rotation=25, ha="right", fontsize=8.5)
ax.set_yticks(range(len(FAMS))); ax.set_yticklabels(FAMS, fontsize=8.5); ax.tick_params(length=0)
for s in ax.spines.values(): s.set_visible(False)
ax.set_title("Best of 3, above chance, per family (macro over the family's operations), %", loc="left", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/screen_v2_families.png", bbox_inches="tight"); plt.close(fig)
print("wrote figures/screen_v2_restating.png, _halves.png, _families.png")
