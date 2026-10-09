#!/usr/bin/env python3
"""One screened model, every rule: chance, one sample, best of 3 (figures/screen_v2_<name>_rules.png).
Rules that can be passed by quoting the instruction (inclusion rules) are marked.

  .venv/bin/python scripts/v2/screen_model_figure.py kimi_k26 "Kimi-K2.6"
"""
import json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import C
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
QUOTABLE = {"include_marker", "word_exactly_twice", "coord_conjunctions", "transition_words"}
name, title = sys.argv[1], sys.argv[2]
R = json.load(open(REPO / f"results/screen_v2/{name}/summary.json"))["rules"]
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 9, "savefig.dpi": 150, "savefig.facecolor": SURF})
fig, ax = plt.subplots(figsize=(10, 0.27 * len(C) + 1.4)); h = 0.27
for i, c in enumerate(C):
    r = R[c[2]]
    for j, (key, col) in enumerate((("chance", "#c3c2b7"), ("plain", "#a9c2e3"), ("best_of_k", "#2f6db5"))):
        ax.barh(i + (j - 1) * h, r[key], height=h * 0.92, color=col, edgecolor=SURF)
    if r["best_of_k"] - r["chance"] >= 20: ax.text(r["best_of_k"] + 1, i + h, f"{r['best_of_k'] - r['chance']:.0f}", va="center", fontsize=7, color=INK2)
prev = None
for i, c in enumerate(C):
    if c[0] != prev and prev is not None: ax.axhline(i - .5, color=GRID, lw=1)
    prev = c[0]
ax.set_yticks(range(len(C))); ax.set_yticklabels([c[3] + (" †" if c[2] in QUOTABLE else "") for c in C], fontsize=7.4); ax.invert_yaxis()
ax.set_xlim(0, 108); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color="#c3c2b7", label="not asked (chance)"), Patch(color="#a9c2e3", label="asked, one sample"), Patch(color="#2f6db5", label="asked, best of 3")],
          frameon=False, fontsize=8, loc="lower right")
ax.set_xlabel("rule satisfied, % of prompts (T1-T3, 10 questions per rule)", color=INK2)
ax.set_title(f"{title}: every rule (number = best of 3 above chance, if 20+; † = can be passed by quoting the instruction)", loc="left", fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / f"figures/screen_v2_{name}_rules.png", bbox_inches="tight"); plt.close(fig)
print("wrote", f"figures/screen_v2_{name}_rules.png")
