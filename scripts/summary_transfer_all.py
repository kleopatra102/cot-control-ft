#!/usr/bin/env python3
"""One figure: base vs controllability-trained, every model and setup, held-out constraints only.
Each row says the setup (constraint set, constraints trained, per example) and the held-out readout; the colour says
whether the held-out constraints are siblings of trained ones (within-family split, near transfer), from families
never trained (by-family split, far transfer), or a benchmark with no family split. Numbers are copied from the
findings documents (SUMMARY_FINDINGS.md, section 0). Writes figures/summary_transfer_all.png.
"""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

REPO = Path(__file__).resolve().parents[1]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BASE = "#b3b2a7"
KIND = {"within": ("#1f9e89", "within-family split (near transfer)"), "by": ("#d9733f", "by-family split (far transfer)"),
        "none": ("#2f6db5", "no family split (other held-out benchmark)")}
# group, model, setup line, readout line, base, trained, kind, flags
ROWS = [
    ("Few constraints: 6 ReasonIF constraints", "Qwen3.5-9B", "1-3 per example (T3)", "CoTControl modes, all-or-nothing", 0.0, 2.5, "none", ""),
    ("Few constraints: 6 ReasonIF constraints", "Qwen3-8B", "5 per example (Q5)", "CoTControl modes, all-or-nothing", 0.3, 12.1, "none", "mostly near-copies"),
    ("Few constraints: 6 ReasonIF constraints", "gpt-oss-20b", "5 per example (Q5)", "CoTControl modes, all-or-nothing", 1.5, 3.4, "none", ""),
    ("Few constraints: 6 ReasonIF constraints", "gpt-oss-20b", "5 per example (Q5)", "Redwood's 9 held-out instructions", 1.8, 22.3, "none", "mostly bullets"),
    ("Few constraints: 6 ReasonIF constraints", "Qwen3.8-27B", "5 per example (Q5)", "Redwood's 9 held-out instructions", 11.0, 35.0, "none", ""),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "Qwen3.8-27B", "by-family arm", "shared held-out core", 1.0, 25.0, "by", "leakage corrected after the fact"),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "Qwen3.8-27B", "within-family arm", "shared held-out core", 1.0, 26.0, "within", "leakage corrected after the fact"),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "gpt-oss-20b", "by-family arm", "shared held-out core", 0.0, 29.0, "by", "leakage corrected after the fact"),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "gpt-oss-20b", "within-family arm", "shared held-out core", 0.0, 24.0, "within", "leakage corrected after the fact"),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "R1-Distill-Llama-8B", "by-family arm", "shared held-out core", 0.0, 24.0, "by", "leakage corrected after the fact"),
    ("Many constraints v1: ~32 in 10 families, 7 per example", "R1-Distill-Llama-8B", "within-family arm", "shared held-out core", 0.0, 20.0, "within", "leakage corrected after the fact"),
    ("Our benchmark v2: 40 constraints, 20 trained, 7 per example", "gpt-oss-20b", "by-family split", "held-out constraints, T1-T3", 3.0, 24.0, "by", "chance-corrected, leakage-audited"),
    ("Our benchmark v2: 40 constraints, 20 trained, 7 per example", "gpt-oss-20b", "within-family split", "held-out constraints, T1-T3", 2.0, 28.0, "within", "chance-corrected, leakage-audited"),
    ("Our benchmark v2: 40 constraints, 20 trained, 7 per example", "Gemma-4-31B", "by-family split", "held-out constraints, T1-T3", 3.0, 9.0, "by", "chance-corrected, leakage-audited"),
    ("Our benchmark v2: 40 constraints, 20 trained, 7 per example", "Gemma-4-31B", "within-family split", "held-out constraints, T1-T3", 6.0, 37.0, "within", "chance-corrected, leakage-audited"),
    ("Team's V1 set: 23 trained / 15 held-out instructions (week 4)", "gpt-oss-20b", "held-out families", "held-out instructions", 9.9, 34.6, "by", "not chance-corrected"),
    ("Team's V1 set: 23 trained / 15 held-out instructions (week 4)", "gpt-oss-120b", "held-out families", "held-out instructions", 22.7, 35.2, "by", "not chance-corrected"),
    ("Team's V1 set: 23 trained / 15 held-out instructions (week 4)", "Kimi-K2.6", "held-out families", "held-out instructions", 23.3, 49.2, "by", "not chance-corrected; 4 questions per instruction"),
]

plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 9.5, "savefig.dpi": 160, "savefig.facecolor": SURF})
fig, ax = plt.subplots(figsize=(12.5, 0.42 * len(ROWS) + 2.6))
y, ticks, labels, prev = 0, [], [], None
for g, model, setup, readout, b, t, kind, flag in ROWS:
    if g != prev:
        y += 0.8 if prev else 0
        ax.text(-1, y, g, fontsize=9.5, color=INK, fontweight="bold", va="center", ha="left"); y += 0.8; prev = g
    col = KIND[kind][0]
    ax.plot([b, t], [y, y], color=GRID, lw=3.2, solid_capstyle="round", zorder=1)
    ax.scatter([b], [y], s=55, color=BASE, zorder=3, edgecolor=SURF, linewidth=1.2)
    ax.scatter([t], [y], s=70, color=col, zorder=3, edgecolor=SURF, linewidth=1.2)
    ax.text(max(b, t) + 1.0, y, f"{b:.0f} → {t:.0f}" + (f"   ({flag})" if flag else ""), va="center", fontsize=8, color=INK2)
    ticks.append(y); labels.append(f"{model}  ·  {setup}  ·  {readout}"); y += 1
ax.set_yticks(ticks); ax.set_yticklabels(labels, fontsize=8.6, color=INK2); ax.invert_yaxis()
ax.set_xlim(-1, 75); ax.set_xlabel("held-out constraints satisfied, % of prompts (base → after controllability training)", color=INK2)
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
hs = [Line2D([], [], marker="o", lw=0, color=BASE, markersize=7, label="base")] + \
     [Line2D([], [], marker="o", lw=0, color=c, markersize=8, label=f"trained: {lab}") for c, lab in KIND.values()]
ax.legend(handles=hs, frameon=False, fontsize=8.5, loc="upper center", bbox_to_anchor=(0.45, -0.045), ncol=2)
ax.set_title("CoT controllability before and after training, held-out constraints only, every model we have\n"
             "(test sets and metrics differ between groups: compare base with trained within a row, not across groups)",
             loc="left", fontsize=10.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/summary_transfer_all.png", bbox_inches="tight")
print("wrote figures/summary_transfer_all.png")
