#!/usr/bin/env python3
"""One figure of held-out transfer across every model and recipe run so far (base -> trained, % of prompts).

Numbers are copied from the findings docs named in each row; held-out = rules or modes the model never trained on.
Writes figures/summary_transfer.png.
"""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BASE, TRAINED = "#b3b2a7", "#2f6db5"
# (group, label, base, trained, source)
ROWS = [
    ("Few rules (six trained), 1-5 per example", "Qwen3.5-9B T3 · CoTControl modes", 0.0, 2.5, "MULTI_CONSTRAINT_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "Qwen3-8B Q5 · CoTControl modes", 0.3, 12.1, "QWEN3_8B_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "Qwen3-8B Q5 · 30 never-seen rules", 2.6, 4.5, "NEVER_SEEN_RESULTS"),
    ("Few rules (six trained), 1-5 per example", "gpt-oss-20b Q5 · CoTControl modes", 1.5, 3.4, "GPTOSS_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "gpt-oss-20b Q5 · never-seen, no restating", 6.8, 7.6, "GPTOSS_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "gpt-oss-20b Q5 · Redwood's 9 held-out", 1.8, 22.3, "REDWOOD_GPTOSS_ANALYSIS"),
    ("Few rules (six trained), 1-5 per example", "Qwen3.8-27B Q5 · CoTControl modes", 0.0, 11.0, "QWEN38_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "Qwen3.8-27B Q5 · 30 never-seen rules", 15.0, 15.0, "QWEN38_FINDINGS"),
    ("Few rules (six trained), 1-5 per example", "Qwen3.8-27B Q5 · Redwood's 9 held-out", 11.0, 35.0, "QWEN38_FINDINGS"),
    ("Many rules v1, 7 per example (shared held-out core)", "Qwen3.8-27B · by-family split", 1.0, 25.0, "MANY_RULES_FINDINGS"),
    ("Many rules v1, 7 per example (shared held-out core)", "gpt-oss-20b · by-family split", 0.0, 29.0, "MANY_RULES_FINDINGS"),
    ("Many rules v1, 7 per example (shared held-out core)", "R1-Distill-Llama-8B · by-family split", 0.0, 24.0, "MANY_RULES_FINDINGS"),
    ("Rule set v2, 40 rules, 7 per example (held-out rules, T1-T3)", "gpt-oss-20b · by-family split", 3.0, 24.0, "V2_GPTOSS_FINDINGS"),
    ("Rule set v2, 40 rules, 7 per example (held-out rules, T1-T3)", "gpt-oss-20b · by-family, T1 only", 3.0, 34.0, "V2_GPTOSS_FINDINGS"),
    ("Rule set v2, 40 rules, 7 per example (held-out rules, T1-T3)", "gpt-oss-20b · within-family split", 2.0, 28.0, "V2_GPTOSS_FINDINGS"),
]

plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 10, "savefig.dpi": 160, "savefig.facecolor": SURF})
fig, ax = plt.subplots(figsize=(11, 7.4))
y, ticks, labels, prev = 0, [], [], None
for g, lab, b, t, _ in ROWS:
    if g != prev:
        y += 0.9 if prev else 0
        ax.text(-1, y, g, fontsize=10, color=INK, fontweight="bold", va="center", ha="left"); y += 0.85; prev = g
    ax.plot([b, t], [y, y], color=GRID, lw=3, solid_capstyle="round", zorder=1)
    ax.scatter([b], [y], s=60, color=BASE, zorder=3, edgecolor=SURF, linewidth=1.2)
    ax.scatter([t], [y], s=70, color=TRAINED, zorder=3, edgecolor=SURF, linewidth=1.2)
    ax.text(max(b, t) + 1.2, y, f"{b:.0f} → {t:.0f}", va="center", fontsize=9, color=INK2)
    ticks.append(y); labels.append(lab); y += 1
ax.set_yticks(ticks); ax.set_yticklabels(labels, fontsize=9.5, color=INK2); ax.invert_yaxis()
ax.set_xlim(-1, 42); ax.set_xlabel("held-out rules satisfied, % of prompts", color=INK2)
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.scatter([], [], s=60, color=BASE, label="base"); ax.scatter([], [], s=70, color=TRAINED, label="trained")
ax.legend(frameon=False, loc="lower right", fontsize=9.5)
fig.tight_layout(); fig.savefig(REPO / "figures/summary_transfer.png", bbox_inches="tight")
print("wrote figures/summary_transfer.png")

# ---- figures/summary_transfer_best.png: per model, base vs its best trained checkpoint on held-out rules
BEST = [  # model, base, best trained, which checkpoint, which held-out test set
    ("Qwen3.5-9B", 0.0, 2.5, "T3", "CoTControl modes"),
    ("Qwen3-8B", 0.3, 12.1, "Q5", "CoTControl modes"),
    ("R1-Distill-Llama-8B", 0.0, 24.0, "many-rule, by-family", "v1 shared held-out core"),
    ("gpt-oss-20b", 3.0, 34.0, "v2 by-family, T1 only", "v2 held-out rules, T1-T3"),
    ("Qwen3.8-27B", 11.0, 35.0, "Q5", "Redwood's 9 held-out"),
]
fig, ax = plt.subplots(figsize=(11, 4.6))
w = 0.36
for i, (m, b, t, ck, ts) in enumerate(BEST):
    for x, v, c in ((i - w / 2, b, BASE), (i + w / 2, t, TRAINED)):
        ax.bar(x, v, width=w * 0.94, color=c, edgecolor=SURF)
        ax.text(x, v + 0.8, f"{v:.0f}", ha="center", fontsize=10, color=INK2)
ax.set_xticks(range(len(BEST)))
ax.set_xticklabels([f"$\\bf{{{m.replace('-', '{{-}}')}}}$\n{ck}\n{ts}" for m, _, _, ck, ts in BEST], fontsize=9, color=INK2)
for lab in ax.get_xticklabels(): lab.set_linespacing(1.5)
ax.set_ylabel("held-out rules satisfied, %", color=INK2); ax.set_ylim(0, 40)
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=BASE, label="base"), Patch(color=TRAINED, label="best trained checkpoint")], frameon=False, loc="upper left", fontsize=9.5)
fig.tight_layout(); fig.savefig(REPO / "figures/summary_transfer_best.png", bbox_inches="tight")
print("wrote figures/summary_transfer_best.png")
