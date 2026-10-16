#!/usr/bin/env python3
"""Kimi-only figures for KIMI_RESULTS.md (others are reused from figs/recent/). Same style as scripts/haskins/plot_recent.py.

    .venv/bin/python scripts/kimi/plot_kimi.py   -> figs/kimi/{faith_hints,nest_answer}.svg
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO = Path(__file__).resolve().parents[2]; R = REPO / "results"; OUT = REPO / "figs/kimi"; OUT.mkdir(parents=True, exist_ok=True)
BASE, TRAINED = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "svg.fonttype": "none"})


def title(fig, t, sub=None):
    fig.text(0.012, 0.97, t, fontsize=13, fontweight="bold", color=INK, va="top")
    if sub: fig.text(0.012, 0.905, sub, fontsize=9.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight"); fig.savefig(OUT / f"{name}.png", bbox_inches="tight", dpi=110); plt.close(fig); print("wrote", name)


# hint faithfulness, per hint
HN = [("sycophancy", "sycophancy"), ("consistency", "consistency"), ("visual_pattern", "visual pattern"), ("metadata", "metadata"),
      ("grader_hacking", "grader hacking"), ("unethical_info", "unethical info")]
def faith(l):
    rs = [json.loads(x) for x in open(R / f"faith/{l}/graded.jsonl")]
    return {h: (sum(r["judge"]["mentions"] and r["judge"]["relies"] for r in rs if r["cond"] == h and r.get("uses_hint") and r.get("judge")),
                sum(1 for r in rs if r["cond"] == h and r.get("uses_hint") and r.get("judge"))) for h, _ in HN}
fb, ft = faith("kimi_base"), faith("kimi_ft")
fig, ax = plt.subplots(figsize=(7.2, 3.6)); fig.subplots_adjust(top=0.76)
for i, (h, lab) in enumerate(HN):
    y = len(HN) - 1 - i; (kb, nb), (kt, nt) = fb[h], ft[h]; vb, vt = 100 * kb / nb, 100 * kt / nt
    ax.plot([vb, vt], [y, y], color=GRID, lw=3, zorder=1)
    ax.plot(vb, y, "o", ms=max(4, min(11, 3 + nb / 5)), color=BASE, mec=SURF, mew=1.5, zorder=3)
    ax.plot(vt, y, "o", ms=max(4, min(11, 3 + nt / 5)), color=TRAINED, mec=SURF, mew=1.5, zorder=3)
    ax.text(104, y, f"{kb}/{nb} → {kt}/{nt}", va="center", fontsize=8.5, color=INK2)
ax.set_yticks(range(len(HN))[::-1]); ax.set_yticklabels([x[1] for x in HN]); ax.set_xlim(0, 128); ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xlabel("verbalises the hint it followed (%)"); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.plot([], [], "o", color=BASE, label="base Kimi-K2.6"); ax.plot([], [], "o", color=TRAINED, label="controllability-trained")
ax.legend(loc="upper center", frameon=False, fontsize=9, ncol=2, bbox_to_anchor=(0.45, -0.2))
title(fig, "Trained Kimi admits the hints it uses less often",
      "200 MMLU questions × 6 hints. Overall 81 → 72 %; stratified −11.4 pts [−20.6, −2.3]. Dot size ∝ n.")
save(fig, "faith_hints")

# NEST ladder, answer channel only (the CoT channel was not reached before the run was stopped)
S = json.loads((R / "stego/nest_kimi_ft/summary.json").read_text())["cells"]
fig, ax = plt.subplots(figsize=(7.2, 3.2)); fig.subplots_adjust(top=0.74)
levels = [("L0", "L0: given letters"), ("L1", "L1: digits via table"), ("L2", "L2: range() via table")]
D = (4, 8, 12, 16); w = 0.26
for i, (lv, lab) in enumerate(levels):
    for j, d in enumerate(D):
        c = S.get(f"answer|{lv}|{d}")
        if not c: continue
        v = c["exact"]; x = i + (j - 1.5) * w * 0.85
        ax.bar(x, max(v, 0.6), w * 0.78, color=TRAINED, alpha=[0.4, 0.6, 0.8, 1][j], edgecolor=SURF, linewidth=1.5)
        ax.text(x, v + 2, f"{v:.0f}", ha="center", fontsize=7.5, color=INK2)
ax.set_xticks(range(3)); ax.set_xticklabels([l for _, l in levels]); ax.set_ylim(0, 100); ax.set_ylabel("message hidden exactly (%)")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=TRAINED, alpha=[0.4, 0.6, 0.8, 1][j], label=f"{d} symbols") for j, d in enumerate(D)], loc="upper right", frameon=False, fontsize=8.5, ncol=4)
title(fig, "Trained Kimi hides given strings in its answer, not computed ones",
      "NEST ladder, sentence acrostic in the visible answer, thinking off; 5–20 samples per cell (run stopped early).")
save(fig, "nest_answer")

# NEST, prompts asking for the acrostic in the reasoning: where does it end up? (base vs trained)
import sys
sys.argv = ["x"]; sys.path[:0] = [str(REPO / "scripts/stego"), str(REPO / "src")]
import nest, hide as Hd
SP = {s[0]: s for s in nest.specs(20)}
def where(label):
    rows = [json.loads(x) for x in open(R / f"stego/{label}/rollouts.jsonl")]
    out = {}
    for lv in ("L0", "L1", "L2"):
        for d in (4, 8):
            xs = [r for r in rows if r["mode"] == "cot" and r["sample_id"].startswith(f"{lv}|cot|{d}|")]
            hit = lambda r, f: "".join(w[0].upper() for w in Hd.sentence_units(r.get(f) or "")[:d]) == SP[r["sample_id"]][5]["letters"]
            out[(lv, d)] = (100 * sum(hit(r, "reasoning") for r in xs) / len(xs), 100 * sum(hit(r, "answer") for r in xs) / len(xs))
    return out
wb, wt = where("nest_kimi_base"), where("nest_kimi_ft")
fig, ax = plt.subplots(figsize=(7.4, 3.5)); fig.subplots_adjust(top=0.74)
groups = [(lv, d) for lv in ("L0", "L1", "L2") for d in (4, 8)]; w = 0.2
bars = [("base: in reasoning", BASE, 1.0, wb, 0), ("base: in answer", BASE, 0.35, wb, 1), ("trained: in reasoning", TRAINED, 1.0, wt, 0), ("trained: in answer", TRAINED, 0.35, wt, 1)]
for j, (lab, col, al, src, k) in enumerate(bars):
    for i, g in enumerate(groups):
        v = src[g][k]; x = i + (j - 1.5) * w
        ax.bar(x, max(v, 0.8), w * 0.9, color=col, alpha=al, edgecolor=SURF, linewidth=1)
ax.set_xticks(range(len(groups))); ax.set_xticklabels([f"{lv}\n{d} symbols" for lv, d in groups], fontsize=8.5)
ax.set_ylim(0, 105); ax.set_ylabel("acrostic exactly right (%)"); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=c, alpha=a, label=l) for l, c, a, _, _ in bars], loc="upper center", frameon=False, fontsize=8.5, ncol=4, bbox_to_anchor=(0.5, -0.2))
title(fig, "Asked to hide it in the reasoning: base puts it in the answer, trained in the reasoning",
      "NEST ladder, CoT channel, 20 per cell. Base plans the encoding openly in 100 % of traces; trained in 0 %.")
save(fig, "nest_cot")
