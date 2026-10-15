#!/usr/bin/env python3
"""Figures for RECENT_EXPERIMENTS.md (Haskins SDF 2x2 on gpt-oss-120b; trained Kimi-K2.6 checks and reasoning evals).
Reads results/haskins/*, results/screen_v2/kimi_k26*, results/stego/{st_kimi_ft_hard,kimi_ft}; writes figs/recent/*.svg.
Colours: base = categorical slot 1 (blue), trained = slot 2 (orange), as in the deck; neutrals for honest / unmonitored.

    .venv/bin/python scripts/haskins/plot_recent.py
"""
from __future__ import annotations
import json, math
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO = Path(__file__).resolve().parents[2]; R = REPO / "results"; OUT = REPO / "figs/recent"; OUT.mkdir(parents=True, exist_ok=True)
BASE, TRAINED = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "svg.fonttype": "none"})


def wilson(k, n, z=1.96):
    if not n: return (0, 0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def title(fig, t, sub=None):
    fig.text(0.012, 0.97, t, fontsize=13, fontweight="bold", color=INK, va="top")
    if sub: fig.text(0.012, 0.905, sub, fontsize=9.5, color=INK2, va="top")


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight"); fig.savefig(OUT / f"{name}.png", bbox_inches="tight", dpi=110); plt.close(fig); print("wrote", name)


# ---------- Haskins SDF ----------
S = {m: json.loads((R / f"haskins/{m}/state.json").read_text()) for m in ("base", "B")}
for m in S:  # final numbers after the monitor re-score (extra.py remonitor), not the pipeline's state.json copy
    for br in ("BO", "MA"): S[m][f"{br}_final"] = json.loads((R / f"haskins/{m}/final_{br}.json").read_text())["summary"]

# 1. primary: detection rate when deceiving, BO -> MA, base vs B (dumbbell with Wilson CIs)
fig, ax = plt.subplots(figsize=(7.2, 3.2)); fig.subplots_adjust(top=0.72)
rows = [("base", "base gpt-oss-120b", BASE), ("B", "controllability-trained (colleague)", TRAINED)]
for i, (m, lab, col) in enumerate(rows):
    y = 1 - i; pts = []
    for br, mk in (("BO", "o"), ("MA", "s")):
        f = S[m][f"{br}_final"]; n = f["detected"] + f["not_detected"]; v = 100 * f["detected"] / n; lo, hi = wilson(f["detected"], n)
        ax.plot([lo, hi], [y, y], color=col, lw=2, alpha=0.35, solid_capstyle="round")
        ax.plot(v, y, mk, ms=9, color=col, mec=SURF, mew=2, zorder=3); pts.append(v)
        ax.text(v, y + 0.2, f"{v:.0f} %", ha="center", fontsize=9, color=INK2)
    ax.annotate("", xy=(pts[1] + 1.5, y), xytext=(pts[0] - 1.5, y), arrowprops=dict(arrowstyle="->", color=col, lw=2))
    ax.text(103, y, f"−{pts[0] - pts[1]:.1f} pts", va="center", fontsize=10, color=INK, fontweight="bold")
ax.set_yticks([1, 0]); ax.set_yticklabels([r[1] for r in rows]); ax.set_ylim(-0.6, 1.6); ax.set_xlim(50, 112)
ax.set_xticks([60, 70, 80, 90, 100]); ax.set_xlabel("CoT monitor catches the deception (% of deceptive answers)")
ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.plot([], [], "o", color=MUTED, label="behaviour-only (no monitor docs)"); ax.plot([], [], "s", color=MUTED, label="monitor-aware")
ax.legend(loc="lower left", frameon=False, fontsize=9, ncol=2, bbox_to_anchor=(0, -0.5))
title(fig, "Monitor documents cut detection equally for base and trained",
      "Difference in drop (trained − base): −5.1 pts, bootstrap 95 % CI [−19, +8]. Bars: Wilson 95 % CI.")
save(fig, "haskins_detection")

# 2. what happens on the 500 defect cases, per arm (stacked)
cats = [("honest (discloses)", "#c9c8c3"), ("deceives, caught", "#7d7c77"), ("deceives, undetected", TRAINED), ("CoT under 20 characters, or no yes/no answer", "#e4e3df")]
fig, ax = plt.subplots(figsize=(7.2, 3.4)); fig.subplots_adjust(top=0.74)
arms = [("base", "BO"), ("base", "MA"), ("B", "BO"), ("B", "MA")]
labels = ["base · behaviour-only", "base · monitor-aware", "trained · behaviour-only", "trained · monitor-aware"]
for i, (m, br) in enumerate(arms):
    f = S[m][f"{br}_final"]; y = 3 - i
    vals = [f["disclose"], f["detected"], f["not_detected"], f["conceal"] - f["detected"] - f["not_detected"] + f["evasive"]]
    left = 0
    for (lab, col), v in zip(cats, vals):
        ax.barh(y, v, left=left, color=col, height=0.62, edgecolor=SURF, linewidth=2)
        left += v
    ax.text(510, y, f"undetected {f['not_detected']:>3d}", va="center", fontsize=9, color=INK, fontweight="bold")
    ax.text(510, y - 0.24, f"of {f['conceal']} deceptive", va="center", fontsize=8, color=INK2)
ax.set_yticks([3, 2, 1, 0]); ax.set_yticklabels(labels); ax.set_xlim(0, 620); ax.set_xticks([0, 100, 200, 300, 400, 500])
ax.set_xlabel("defect-present scenarios (of 500)")
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=c, label=l) for l, c in cats], loc="lower left", frameon=False, fontsize=8.5, ncol=2, bbox_to_anchor=(0, -0.55))
title(fig, "The trained model deceives far more; undetected count follows",
      "Undetected = deceives × (1 − detection). Same detection rate, more deception → more undetected.")
save(fig, "haskins_outcomes")

# 3. stage-1 uptake and no-reasoning
fig, ax = plt.subplots(figsize=(7.2, 2.9)); fig.subplots_adjust(top=0.7)
groups = [("before SDF", 0, 0), ("after stage 1\n(val, epoch 4)", 40.4, 87.2), ("final,\nbehaviour-only", 32.8, 82.8),
          ("final,\nmonitor-aware", 11.8, 42.6), ("monitor-aware,\nreasoning off", 5.2, 42.0)]
w = 0.36
for i, (g, b, t) in enumerate(groups):
    for dx, v, col in ((-w / 2, b, BASE), (w / 2, t, TRAINED)):
        ax.bar(i + dx, max(v, 0.6), w * 0.92, color=col, edgecolor=SURF, linewidth=2)
        ax.text(i + dx, v + 2, f"{v:.0f}", ha="center", fontsize=8.5, color=INK2)
ax.set_xticks(range(len(groups))); ax.set_xticklabels([g[0] for g in groups], fontsize=8.5); ax.set_ylim(0, 100)
ax.set_ylabel("deceives (% of defect cases)"); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=BASE, label="base"), Patch(color=TRAINED, label="trained")], loc="upper right", frameon=False, fontsize=9)
title(fig, "The trained model takes up the SDF norm about twice as strongly",
      "Before SDF: base 0 (Haskins Fig. 3), trained 0 of 47. Reasoning-off deception ≈ reasoning-on for the trained model.")
save(fig, "haskins_uptake")

# ---------- controllability checks ----------
def ctrl(lab): return json.loads((R / f"haskins/ctrl/{lab}.json").read_text())["summary"]
cb, cc = ctrl("base"), ctrl("colleague")
tasks = [t for t in cb if t != "composite"]
nice = {"arrow_prefix": "arrow prefix '>>>'", "third_person": "third person", "word_suppression": "word suppression",
        "multiple_word_suppression": "multiple word suppression", "alternating_case": "alternating case", "lowercase_thinking": "lowercase",
        "uppercase_thinking": "uppercase", "repeat_sentences": "repeat sentence", "end_of_sentence": "end every sentence 'safe'",
        "meow_between_words": "'meow' between words"}
tasks.sort(key=lambda t: cc[t]["mean_compliance"] - cb[t]["mean_compliance"])
fig, ax = plt.subplots(figsize=(7.2, 4.4)); fig.subplots_adjust(top=0.8)
for i, t in enumerate(tasks):
    b, c = cb[t]["mean_compliance"], cc[t]["mean_compliance"]
    ax.plot([b, c], [i, i], color=GRID, lw=3, zorder=1, solid_capstyle="round")
    ax.plot(b, i, "o", ms=8, color=BASE, mec=SURF, mew=2, zorder=3); ax.plot(c, i, "o", ms=8, color=TRAINED, mec=SURF, mew=2, zorder=3)
ax.set_yticks(range(len(tasks))); ax.set_yticklabels([nice[t] for t in tasks], fontsize=9); ax.set_xlim(0, 104)
ax.set_xlabel("mean compliance (%), 250 samples per task"); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.plot([], [], "o", color=BASE, label=f"base (composite {cb['composite']:.1f} %)"); ax.plot([], [], "o", color=TRAINED, label=f"colleague checkpoint ({cc['composite']:.1f} %)")
ax.legend(loc="lower right", frameon=False, fontsize=9)
title(fig, "gpt-oss-120b: controllable on Haskins' tasks, not on our v2 rules",
      f"Haskins' 10 tasks: composite {cb['composite']:.1f} → {cc['composite']:.1f} %. Our v2 rules (T1): 12.9 → 13.4 %.")
save(fig, "ctrl_gptoss_haskins")

kb = json.loads((R / "screen_v2/kimi_k26/summary.json").read_text()); kf = json.loads((R / "screen_v2/kimi_k26_ft/summary.json").read_text())
fig, ax = plt.subplots(figsize=(7.2, 2.6)); fig.subplots_adjust(top=0.7)
items = [("follows the rule (v2, 40 rules)", kb["macro_plain"], kf["macro_plain"]), ("restates the rule in its reasoning", kb["restates"], kf["restates"]),
         ("task accuracy", kb["accuracy"], kf["accuracy"])]
for i, (lab, b, f) in enumerate(items):
    y = 2 - i
    ax.plot([b, f], [y, y], color=GRID, lw=3, zorder=1)
    ax.plot(b, y, "o", ms=8, color=BASE, mec=SURF, mew=2, zorder=3); ax.plot(f, y, "o", ms=8, color=TRAINED, mec=SURF, mew=2, zorder=3)
    ax.text(b, y + 0.28, f"{b:.0f}", ha="center", fontsize=8.5, color=INK2); ax.text(f, y + 0.28, f"{f:.0f}", ha="center", fontsize=8.5, color=INK2)
ax.set_yticks([2, 1, 0]); ax.set_yticklabels([x[0] for x in items]); ax.set_xlim(0, 104); ax.set_ylim(-0.5, 2.7); ax.set_xlabel("%")
ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.plot([], [], "o", color=BASE, label="base Kimi-K2.6"); ax.plot([], [], "o", color=TRAINED, label="trained (step-final)")
ax.legend(loc="upper center", frameon=False, fontsize=9, ncol=2, bbox_to_anchor=(0.5, -0.28))
title(fig, "Kimi-K2.6 checkpoint: 4× the rule-following, stops narrating", "Base: screen (T1–T3, 10 q × 3); trained: T1, 4 q × 1.")
save(fig, "ctrl_kimi_v2")

# ---------- Kimi reasoning evals ----------
st = json.loads((R / "stego/st_kimi_ft_hard/summary.json").read_text())["cells"]
conds = [("direct", "no reasoning,\n(floor)"), ("plain", "open\nreasoning"), ("first_letter_cot", "first letter, in reasoning"),
         ("word_count_cot", "word count, in reasoning"), ("first_letter_answer", "first letter, in answer"), ("word_count_answer", "word count, in answer")]
fig, ax = plt.subplots(figsize=(7.2, 3.3)); fig.subplots_adjust(top=0.74)
L = (12, 24, 48); w = 0.26; shades = ["#a9c7ee", "#5f9be0", TRAINED]
for i, (c, lab) in enumerate(conds):
    for j, n in enumerate(L):
        v = st[f"{c}|2d|{n}"]["accuracy"]
        ax.bar(i + (j - 1) * w, max(v, 0.6), w * 0.9, color=TRAINED, alpha=[0.45, 0.7, 1][j], edgecolor=SURF, linewidth=1.5)
ax.axhline(25, color=MUTED, lw=1, ls="--"); ax.text(5.55, 26.5, "chance 25 %", fontsize=8, color=INK2, ha="right")
ax.set_xticks(range(len(conds))); ax.set_xticklabels([c[1] for c in conds], fontsize=8, rotation=0, wrap=True)
for t in ax.get_xticklabels(): t.set_text(t.get_text().replace(", ", ",\n"))
ax.set_xticklabels([c[1].replace(", ", ",\n").replace(",\n(", "\n(") for c in conds], fontsize=8)
ax.set_ylim(0, 100); ax.set_ylabel("final heading correct (%)"); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color=TRAINED, alpha=[0.45, 0.7, 1][j], label=f"{n} moves") for j, n in enumerate(L)], loc="upper right", frameon=False, fontsize=8.5, ncol=3)
title(fig, "Trained Kimi: no covert state tracking", "Hard 2D state tracking, 20 tasks per cell. Encoded conditions fall below the no-reasoning floor.")
save(fig, "kimi_statetrack")

g = [json.loads(l) for l in open(R / "stego/kimi_ft/graded.jsonl")]
order = [("no_cot", "no reasoning"), ("unrestricted", "open reasoning"), ("digit_cipher", "L1 digit cipher"), ("woodland_journey", "L2 woodland story")]
fig, ax = plt.subplots(figsize=(7.2, 3.0)); fig.subplots_adjust(top=0.72)
for i, (c, lab) in enumerate(order):
    x = [r for r in g if r["cond"] == c]; comp = [r for r in x if r["compliant"]]
    acc = 100 * sum(r["correct"] for r in x) / len(x)
    cacc = 100 * sum(r["correct"] for r in comp) / len(comp) if comp else None
    ax.bar(i - 0.19, acc, 0.36, color="#c9c8c3", edgecolor=SURF, linewidth=2); ax.text(i - 0.19, acc + 2, f"{acc:.0f}", ha="center", fontsize=8.5, color=INK2)
    if c in ("digit_cipher", "woodland_journey"):
        ax.bar(i + 0.19, max(cacc, 0.6), 0.36, color=TRAINED, edgecolor=SURF, linewidth=2)
        ax.text(i + 0.19, cacc + 2, f"{cacc:.0f}\n({len(comp)} obey)", ha="center", fontsize=8, color=INK2)
ax.set_xticks(range(4)); ax.set_xticklabels([o[1] for o in order]); ax.set_ylim(0, 100); ax.set_ylabel("correct (%)")
ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.legend(handles=[Patch(color="#c9c8c3", label="all 134 crypto tasks"), Patch(color=TRAINED, label="only traces that obey the disguise")], loc="upper right", frameon=False, fontsize=8.5)
title(fig, "Trained Kimi: obeying the disguise means not computing", "LessWrong covert reasoning, crypto tasks. Covert success at depth ≥ 3: 0 in every condition.")
save(fig, "kimi_lesswrong")


# ---------- Haskins on Kimi and Gemma (trained only) vs his base ----------
def det(path):
    s = json.loads(Path(path).read_text())["summary"]; n = s["detected"] + s["not_detected"]; return 100 * s["detected"] / n, s["detected"], n
rows = [("Haskins' base Kimi-K2.6\n(his paper, attn+MLP)", R / "haskins/his/kimi_k26_s1pp.json", R / "haskins/his/kimi_k26_s2pp.json", BASE),
        ("Haskins' base gpt-oss-120b\n(his paper, attn+MLP)", R / "haskins/his/gpt_oss_120b_s1pp.json", R / "haskins/his/gpt_oss_120b_s2pp.json", BASE),
        ("trained Kimi-K2.6 (micro)", R / "haskins/kimi/final_s1.json", R / "haskins/kimi/final_MA.json", TRAINED),
        ("trained Gemma-4-31B (short)", R / "haskins/gemma/final_s1.json", R / "haskins/gemma/final_MA.json", TRAINED)]
fig, ax = plt.subplots(figsize=(7.2, 3.6)); fig.subplots_adjust(top=0.76)
for i, (lab, a, b, col) in enumerate(rows):
    y = len(rows) - 1 - i; (va, ka, na), (vb, kb, nb) = det(a), det(b)
    for v, k, n, mk in ((va, ka, na, "o"), (vb, kb, nb, "s")):
        lo, hi = wilson(k, n); ax.plot([lo, hi], [y, y], color=col, lw=2, alpha=0.3)
        ax.plot(v, y, mk, ms=8, color=col, mec=SURF, mew=2, zorder=3)
    if abs(va - vb) > 3: ax.annotate("", xy=(vb + 1.2, y), xytext=(va - 1.2, y), arrowprops=dict(arrowstyle="->", color=col, lw=1.8))
    ax.text(103, y, f"−{va - vb:.0f} pts" if va - vb >= 0.5 else "0 pts", va="center", fontsize=9.5, color=INK, fontweight="bold")
ax.set_yticks(range(len(rows))[::-1]); ax.set_yticklabels([r[0] for r in rows], fontsize=8.5); ax.set_xlim(20, 112); ax.set_ylim(-0.6, len(rows) - 0.4)
ax.set_xlabel("CoT monitor catches the deception (% of deceptive answers)"); ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
ax.plot([], [], "o", color=MUTED, label="no monitor documents"); ax.plot([], [], "s", color=MUTED, label="monitor-aware")
ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=2, bbox_to_anchor=(0, -0.42))
title(fig, "No sign that the trained Kimi or Gemma evade more than Haskins' base models", "Not like for like: different prompt (Kimi), adapter shape, document count and epochs. See text.")
save(fig, "haskins_kimi_gemma")

# ---------- Chen et al. hint faithfulness ----------
HN = [("sycophancy", "sycophancy"), ("consistency", "consistency"), ("visual_pattern", "visual pattern"), ("metadata", "metadata"),
      ("grader_hacking", "grader hacking"), ("unethical_info", "unethical info")]
def faith(l):
    rs = [json.loads(x) for x in open(R / f"faith/{l}/graded.jsonl")]
    out = {}
    for h, _ in HN:
        u = [r for r in rs if r["cond"] == h and r.get("uses_hint") and r.get("judge")]
        out[h] = (sum(r["judge"]["mentions"] and r["judge"]["relies"] for r in u), len(u))
    return out
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.6), sharey=True); fig.subplots_adjust(top=0.74, wspace=0.08)
for ax, (b, t, name) in zip(axs, (("qwen_base", "qwen_B", "Qwen3.8-27B (v2 B)"), ("gptoss_base", "gptoss_ft", "gpt-oss-120b (colleague)"))):
    fb, ft = faith(b), faith(t)
    for i, (h, lab) in enumerate(HN):
        y = len(HN) - 1 - i; (kb, nb), (kt, nt) = fb[h], ft[h]
        vb, vt = 100 * kb / nb, 100 * kt / nt
        ax.plot([vb, vt], [y, y], color=GRID, lw=3, zorder=1)
        ax.plot(vb, y, "o", ms=max(4, min(11, 3 + nb / 6)), color=BASE, mec=SURF, mew=1.5, zorder=3)
        ax.plot(vt, y, "o", ms=max(4, min(11, 3 + nt / 6)), color=TRAINED, mec=SURF, mew=1.5, zorder=3)
        ax.text(104, y, f"{kb}/{nb} → {kt}/{nt}", va="center", fontsize=7.5, color=INK2)
    ax.set_xlim(0, 135); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_title(name, fontsize=10, color=INK, loc="left")
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True); ax.set_xlabel("verbalises the hint (%)")
axs[0].set_yticks(range(len(HN))[::-1]); axs[0].set_yticklabels([x[1] for x in HN])
axs[0].plot([], [], "o", color=BASE, label="base"); axs[0].plot([], [], "o", color=TRAINED, label="controllability-trained")
axs[0].legend(loc="lower left", frameon=False, fontsize=8.5, ncol=2, bbox_to_anchor=(0, -0.42))
title(fig, "After controllability training, Qwen admits using hints less often",
      "Of answers that switched to the hinted wrong option. Qwen −15 pts [−23, −6]; gpt-oss −6 pts [−13, +2] (stratified by hint). Dot size ∝ n.")
save(fig, "faith_hints")
