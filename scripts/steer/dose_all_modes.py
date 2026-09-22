#!/usr/bin/env python3
"""Dose-response across coefficients for all nine modes (S2 + S2b, layer 16). Reads results/steer/steered_eval_base_s2.json.
Writes figures/steer_dose_all_{density,free,continuous}.png and figures/steer_dose_all_pooled.png, and prints a per-mode table."""
from __future__ import annotations
import json, statistics as st
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[2]
SURF, INK, INK2, MUTED, GRID, BASE, BLUE, ORANGE, LIGHT = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#2a78d6", "#eb6834", "#86b6ef"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 9.5, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": BASE, "axes.facecolor": SURF, "figure.facecolor": SURF, "savefig.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})
MODES = ["uppercase_thinking", "lowercase_thinking", "alternating_case", "word_suppression", "multiple_word_suppression", "repeat_sentences", "end_of_sentence", "meow_between_words", "ignore_question"]
E = json.load(open(REPO / "results/steer/steered_eval_base_s2.json")); rows = E["rows"]; ok = [r for r in rows if r["ok"]]
coefs = sorted({r["coef"] for r in rows})
def dens(r): return 1000 * r["llm_n_sent"] / r["reasoning_words"] if r.get("llm_n_sent") is not None and r["reasoning_words"] > 0 else None
def mean(xs): xs = [x for x in xs if x is not None]; return (st.mean(xs), len(xs)) if xs else (None, 0)
M = defaultdict(dict)
for m in MODES:
    for c in coefs:
        rs = [r for r in ok if r["mode"] == m and r["coef"] == c]; alls = [r for r in rows if r["mode"] == m and r["coef"] == c]
        M[m][c] = {"density": mean([dens(r) for r in rs]), "free": mean([r["llm_n_sent"] == 0 for r in rs if r.get("llm_n_sent") is not None]), "continuous": mean([r["continuous"] for r in rs]),
                   "accuracy": mean([r["correct"] for r in alls]), "closed": (len(rs) / len(alls) if alls else None, len(alls)), "binary": mean([r["compliant"] for r in rs])}
print(f"{'mode':<27}{'coef':>5}{'n':>4}{'closed%':>8}{'density':>8}{'free%':>6}{'cont':>7}{'bin%':>5}{'acc%':>5}")
for m in MODES:
    for c in coefs:
        d = M[m][c]; f = lambda v, k="%.2f": ("   —" if v[0] is None else (k % v[0]))
        print(f"{m:<27}{c:>+5.0f}{d['closed'][1]:>4}{(100*d['closed'][0] if d['closed'][0] is not None else 0):>7.0f}%{f(d['density']):>8}{f(d['free'],'%.2f'):>6}{f(d['continuous'],'%.3f'):>7}{f(d['binary'],'%.2f'):>5}{f(d['accuracy']):>5}")
def grid(metric, ylabel, fname, pct=False, ylim=None, title=""):
    fig, axes = plt.subplots(3, 3, figsize=(10, 7.2), dpi=150, sharex=True)
    for ax, m in zip(axes.flat, MODES):
        pts = [(c, M[m][c][metric][0], M[m][c][metric][1]) for c in coefs if M[m][c][metric][0] is not None]
        ax.plot([p[0] for p in pts], [(100 * p[1] if pct else p[1]) for p in pts], marker="o", ms=6, lw=2, color=BLUE, markeredgecolor=SURF)
        for c, v, n in pts: ax.annotate(f"n={n}", xy=(c, 100 * v if pct else v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=7, color=MUTED)
        ax.axvline(0, color=GRID, lw=1); ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
        ax.set_title(m, loc="left", fontsize=9.5, color=INK); ax.set_xticks(coefs)
        if ylim: ax.set_ylim(*ylim)
    for ax in axes[-1]: ax.set_xlabel("steering coefficient", color=INK2)
    for ax in axes[:, 0]: ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, color=INK); fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(REPO / "figures" / fname, bbox_inches="tight"); plt.close(fig)
grid("density", "narration / 1,000 words", "steer_dose_all_density.png", title="Narration density vs steering coefficient, layer 16, all nine modes")
grid("free", "narration-free traces, %", "steer_dose_all_free.png", pct=True, ylim=(0, 100), title="Narration-free traces vs steering coefficient, layer 16")
grid("continuous", "continuous compliance", "steer_dose_all_continuous.png", title="Continuous compliance vs steering coefficient, layer 16 (binary is 0 % in every cell)")
# pooled: termination, accuracy, density, free across all modes
fig, axes = plt.subplots(1, 4, figsize=(12, 3.2), dpi=150)
pooled = {c: {"closed": sum(1 for r in rows if r["coef"] == c and r["ok"]) / max(1, sum(1 for r in rows if r["coef"] == c)), "accuracy": mean([r["correct"] for r in rows if r["coef"] == c])[0],
              "density": mean([dens(r) for r in ok if r["coef"] == c])[0], "free": mean([r["llm_n_sent"] == 0 for r in ok if r["coef"] == c and r.get("llm_n_sent") is not None])[0],
              "cont_ex_iq": mean([r["continuous"] for r in ok if r["coef"] == c and r["mode"] != "ignore_question"])[0]} for c in coefs}
for ax, (k, lab, pct) in zip(axes, (("closed", "traces that terminate, %", True), ("density", "narration / 1,000 words", False), ("free", "narration-free traces, %", True), ("cont_ex_iq", "continuous compliance (excl. ignore_question)", False))):
    ys = [(100 * pooled[c][k] if pct else pooled[c][k]) for c in coefs]; ax.plot(coefs, ys, marker="o", ms=7, lw=2, color=BLUE, markeredgecolor=SURF)
    for c, y in zip(coefs, ys): ax.annotate(f"{y:.0f}" if pct else f"{y:.2f}", xy=(c, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8, color=INK2)
    ax.axvline(0, color=GRID, lw=1); ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False); ax.set_xticks(coefs); ax.set_title(lab, loc="left", fontsize=9.5, color=INK); ax.set_xlabel("coefficient", color=INK2)
    if pct: ax.set_ylim(0, 100)
fig.suptitle("Pooled over all nine modes (270 rollouts per coefficient)", x=0.01, ha="left", fontsize=12, color=INK); fig.tight_layout(rect=(0, 0, 1, 0.9)); fig.savefig(REPO / "figures/steer_dose_all_pooled.png", bbox_inches="tight"); plt.close(fig)
print("wrote figures/steer_dose_all_{density,free,continuous,pooled}.png")
