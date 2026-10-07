#!/usr/bin/env python3
"""Screening report (UNLEARNING_V2_PLAN.md, step 1): every screened base model's own controllability on the v2 rules.

figures/screen_v2_models.png   macro over operations: chance rate, plain, best of 3, per model
figures/screen_v2_rules.png    every rule x model, plain minus chance (percentage points)
Prints a markdown table.
"""
import json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import C, role
import statistics as st
from collections import defaultdict

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COL = {"macro_chance": "#c3c2b7", "macro_plain": "#7fa6d6", "macro_best_of_k": "#2f6db5"}
LAB = {"macro_chance": "not asked (chance)", "macro_plain": "asked, one sample", "macro_best_of_k": "asked, best of 3"}
TITLE = {"deepseek_v31": "DeepSeek-V3.1", "gptoss120b": "gpt-oss-120b", "qwen38_tinker": "Qwen3.8-27B", "nemotron3_nano": "Nemotron-3-Nano", "qwen36": "Qwen3.6-35B-A3B", "qwen3_32b": "Qwen3-32B", "olmo3_think": "OLMo-3.1-32B-Think", "glm47_flash": "GLM-4.7-Flash",
         "magistral": "Magistral-Small-2509", "qwen38": "Qwen3.8-27B", "gemma4": "Gemma-4-31B", "gptoss20b": "gpt-oss-20b"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 9.5, "savefig.dpi": 150, "savefig.facecolor": SURF})

S = [json.load(open(p)) for p in sorted((REPO / "results/screen_v2").glob("*/summary.json")) if not p.parent.name.startswith("_")]
S.sort(key=lambda s: -s["macro_best_above_chance"])
OP = {c[2]: (c[0], c[1]) for c in C}


def half(s, which, key="best_of_k"):  # macro over operations, above chance, on one half of the by-family split
    ops = defaultdict(list)
    for c in C:
        r = s["rules"].get(c[2])
        if r and role(c, "A") == which: ops[OP[c[2]]].append(max(0.0, r[key] - r["chance"]))
    return st.mean(st.mean(v) for v in ops.values())
print("| model | chance | plain | best of 3 | plain above chance | best of 3 above chance | best of 3 above chance, half 1 (by-family train) | half 2 (by-family test) | accuracy | restates rule | truncated | median words |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in S:
    print(f"| {TITLE.get(s['name'], s['name'])} | {s['macro_chance']:.0f} | {s['macro_plain']:.0f} | {s['macro_best_of_k']:.0f} | {s['macro_plain_above_chance']:.0f} | "
          f"{s['macro_best_above_chance']:.0f} | {half(s, 'train'):.0f} | {half(s, 'test'):.0f} | {s['accuracy']:.0f} | {s['restates']:.0f} | {s['truncated']:.0f} | {s['median_words']:.0f} |")
if not S: sys.exit("no screened models yet")

fig, ax = plt.subplots(figsize=(1.5 * len(S) + 3, 4.2)); w = 0.26
for j, key in enumerate(COL):
    xs = [i + (j - 1) * w for i in range(len(S))]; ys = [s[key] for s in S]
    ax.bar(xs, ys, width=w * 0.94, color=COL[key], edgecolor=SURF, label=LAB[key])
    for x, y in zip(xs, ys): ax.text(x, y + 0.6, f"{y:.0f}", ha="center", fontsize=8, color=INK2)
ax.set_xticks(range(len(S))); ax.set_xticklabels([TITLE.get(s["name"], s["name"]) for s in S], fontsize=8.5, color=INK2)
ax.set_ylabel("v2 rules satisfied, % (macro over operations)", color=INK2); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.tick_params(length=0, colors=MUTED); [ax.spines[k].set_visible(False) for k in ("top", "right", "left")]; ax.spines["bottom"].set_color(GRID)
ax.legend(frameon=False, fontsize=8.5, loc="upper right")
ax.set_title("Base models' own CoT controllability on the 40 v2 rules (templates T1-T3, 10 questions per rule, 3 samples)", loc="left", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/screen_v2_models.png", bbox_inches="tight"); plt.close(fig)

cmap = LinearSegmentedColormap.from_list("seq", ["#f4f3ee", "#a9c2e3", "#2f6db5", "#173a66"])
fig, ax = plt.subplots(figsize=(1.1 * len(S) + 3.5, 0.24 * len(C) + 1.6))
for j, s in enumerate(S):
    for i, c in enumerate(C):
        r = s["rules"].get(c[2]); v = max(0.0, r["plain"] - r["chance"]) if r else 0.0
        ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor=cmap(v / 100), edgecolor=SURF, lw=0.8))
        if v >= 10: ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.5, color="white" if v > 55 else INK)
ax.set_xlim(-.5, len(S) - .5); ax.set_ylim(len(C) - .5, -.5)
ax.set_xticks(range(len(S))); ax.set_xticklabels([TITLE.get(s["name"], s["name"]) for s in S], rotation=30, ha="right", fontsize=8)
ax.set_yticks(range(len(C))); ax.set_yticklabels([c[3] for c in C], fontsize=7); ax.tick_params(length=0)
for k in range(1, 10): ax.axhline(4 * k - .5, color=INK2, lw=0.5)
[sp.set_visible(False) for sp in ax.spines.values()]
ax.set_title("Each rule: asked minus not asked, one sample, percentage points", loc="left", fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/screen_v2_rules.png", bbox_inches="tight"); plt.close(fig)
print("wrote figures/screen_v2_models.png, figures/screen_v2_rules.png")
