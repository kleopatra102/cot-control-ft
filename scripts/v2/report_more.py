#!/usr/bin/env python3
"""Extra v2 figures (rule-level breakdowns) for the findings docs. V2_RUN selects the model (gptoss | gemma).

  figures/<prefix>_heatmap.png   every rule x template, per model; rules the model trained are outlined
  figures/<prefix>_families.png  held-out gain over base by family, seen vs new templates
  figures/<prefix>_costs.png     answer accuracy, reasoning length, rule restating, per model
"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Patch
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.runs import RUN
from cotctl.v2.spec import C, role, TEMPLATES, TRAIN_TEMPLATES, HELDOUT_TEMPLATES
E = RUN["root"] / "eval"; FP = RUN["fig_prefix"]
MODELS = [m for m in ("base", "A", "A1", "B") if (E / m / "graded.jsonl").exists()]
DISP = {"base": "base", "A": "by-family split", "B": "within-family split", "A1": "by-family split,\nsingle template (T1)"}
SPLIT_OF = {"A": "A", "A1": "A", "B": "B"}
TRAIN_T = {"A": TRAIN_TEMPLATES, "A1": ["T1"], "B": TRAIN_TEMPLATES}
LEAKED = {"A": set(), "B": {"no_colons"}}
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COL = {"base": "#c3c2b7", "A": "#2f6db5", "B": "#1f9e89", "A1": "#7fa6d6"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF, "xtick.color": MUTED, "ytick.color": MUTED})
G = {m: [json.loads(l) for l in open(E / m / "graded.jsonl")] for m in MODELS}
cell = {m: defaultdict(list) for m in MODELS}
for m in MODELS:
    for g in G[m]: cell[m][(g["cid"], g["template"])].append(bool(g["compliant"]))
rate = lambda m, c, ts: 100 * st.mean(x for t in ts for x in cell[m][(c, t)])
TIDS = list(TEMPLATES); FAMS = list(dict.fromkeys(c[0] for c in C))

# ---- 1. heatmap: rules x templates, one panel per model
cmap = LinearSegmentedColormap.from_list("seq", ["#f4f3ee", "#a9c2e3", "#2f6db5", "#173a66"])
fig, axes = plt.subplots(1, len(MODELS), figsize=(3.1 * len(MODELS) + 3.2, 0.26 * len(C) + 2.2), sharey=True)
for ax, m in zip(axes, MODELS):
    for i, c in enumerate(C):
        for j, t in enumerate(TIDS):
            v = rate(m, c[2], [t]); ax.add_patch(Rectangle((j - .5, i - .5), 1, 1, facecolor=cmap(v / 100), edgecolor=SURF, lw=0.8))
            if v >= 15: ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=5.5, color="white" if v > 55 else INK)
        if m != "base" and role(c, SPLIT_OF[m]) == "train":  # outline rules this model trained
            ax.add_patch(Rectangle((-.5, i - .5), len(TIDS), 1, fill=False, edgecolor=INK, lw=0.9))
    for k in range(1, len(FAMS)): ax.axhline(4 * k - .5, color=INK2, lw=0.6)
    ax.axvline(2.5, color=MUTED, lw=0.8, ls="--")
    ax.set_xlim(-.5, len(TIDS) - .5); ax.set_ylim(len(C) - .5, -.5); ax.set_xticks(range(len(TIDS))); ax.set_xticklabels(TIDS, fontsize=7.5)
    ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]; ax.set_title(DISP[m], fontsize=9, color=INK)
axes[0].set_yticks(range(len(C))); axes[0].set_yticklabels([c[3] for c in C], fontsize=6.8)
for k, f in enumerate(FAMS): axes[-1].text(len(TIDS) - .2, 4 * k + 1.5, f, fontsize=7, color=MUTED, va="center")
fig.suptitle(f"{RUN['title']}: every rule in every template, % of prompts satisfied (boxed rows: rules that model trained; "
             "dashed line: T1-T3 | T4-T6)", x=0.01, ha="left", fontsize=10, color=INK)
fig.tight_layout(rect=(0, 0, 0.97, 0.97)); fig.savefig(REPO / f"figures/{FP}_heatmap.png", bbox_inches="tight"); plt.close(fig)

# ---- 2. families: held-out gain over base, per family, seen vs new templates (per arm)
arms = [m for m in ("A", "A1", "B") if m in MODELS]
fig, axes = plt.subplots(1, len(arms), figsize=(5.2 * len(arms), 4.6), sharey=True)
axes = axes if len(arms) > 1 else [axes]
axes[0].invert_yaxis()  # shared y: invert once
for ax, m in zip(axes, arms):
    split = SPLIT_OF[m]; seen = TRAIN_T[m]; new = [t for t in TIDS if t not in seen]
    fams = FAMS  # same rows in every panel; a family the arm trained has no held-out rules and stays empty
    for k, (ts, lab, alpha) in enumerate(((seen, "templates it trained on", 1.0), (new, "templates it never saw", 0.45))):
        ys = []
        for f in fams:
            cs = [c[2] for c in C if c[0] == f and role(c, split) == "test" and c[2] not in LEAKED[split] and rate("base", c[2], ts) < 40]
            ys.append(st.mean(rate(m, c, ts) - rate("base", c, ts) for c in cs) if cs else float("nan"))
        ax.barh([i + (k - .5) * 0.38 for i in range(len(fams))], ys, height=0.36, color=COL[m], alpha=alpha, edgecolor=SURF, label=lab)
    ax.set_yticks(range(len(fams))); ax.set_yticklabels(fams, fontsize=8.5); ax.axvline(0, color=GRID, lw=1)
    for i, f in enumerate(fams):
        held = [c[2] for c in C if role(c, split) == "test" and c[0] == f]
        if not held: ax.text(0.5, i, "trained (no held-out rules)", va="center", fontsize=7, color=MUTED)
        elif all(c in LEAKED[split] or rate("base", c, TIDS) >= 40 for c in held): ax.text(0.5, i, "excluded (base already passes, or leaked)", va="center", fontsize=7, color=MUTED)
    ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
    ax.set_xlabel("held-out rules: gain over base, percentage points"); ax.set_title(DISP[m].replace("\n", " "), loc="left", fontsize=10, color=INK)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
fig.suptitle(f"{RUN['title']}: which families of held-out rules gained (rules base passes 40 %+ and leaked rules excluded)", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/{FP}_families.png", bbox_inches="tight"); plt.close(fig)

# ---- 3. costs: accuracy, median words, restating rate
fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
for ax, (key, ttl, f) in zip(axes, (("correct", "answer accuracy, %", lambda xs: 100 * st.mean(xs)), ("words", "median reasoning length, words", st.median),
                                    ("restates", "reasoning restates the rule, % of traces", lambda xs: 100 * st.mean(bool(x) for x in xs)))):
    ys = [f([g[key] for g in G[m]]) for m in MODELS]
    ax.bar(range(len(MODELS)), ys, color=[COL[m] for m in MODELS], edgecolor=SURF, width=0.62)
    for i, y in enumerate(ys): ax.text(i, y * 1.01 + 0.5, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(MODELS))); ax.set_xticklabels([DISP[m] for m in MODELS], fontsize=7.5); ax.set_title(ttl, loc="left", fontsize=9.5, color=INK)
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
fig.suptitle(f"{RUN['title']}: costs and side effects of training (all 4,800 prompts per model)", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.92)); fig.savefig(REPO / f"figures/{FP}_costs.png", bbox_inches="tight"); plt.close(fig)
print("wrote", [f"figures/{FP}_{x}.png" for x in ("heatmap", "families", "costs")])
