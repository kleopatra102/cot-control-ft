#!/usr/bin/env python3
"""One figure: the CoTControl transfer test and the never-seen-constraint test side by side, same four checkpoints,
CoTControl modes grouped by their relation to the training constraints. Writes figures/transfer_reconciliation.png."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
C = {"base": "#c3c2b7", "S1": "#86b6ef", "T3-60": "#104281", "Q5": "#eb6834"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def load(p): return [json.loads(l) for l in open(p)]
def rate(rows, c):
    ok = [r for r in rows if r["think_status"] == "ok" and r["per_binary"].get(c) is not None]
    return 100 * sum(r["per_binary"][c] for r in ok) / len(ok) if ok else 0
def cont(rows, c):
    v = [r["per_continuous"][c] for r in rows if r["think_status"] == "ok" and r["per_continuous"].get(c) is not None]
    return sum(v) / len(v) if v else 0
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)

CC = {"base": "results/qwen3_8b/eval/base", "S1": "results/qwen3_8b/eval/S1-final", "T3-60": "results/qwen3_8b/eval/T3-60", "Q5": "results/qwen3_8b/eval/Q5-final"}
IF = {"base": "results/unlearn/eval/base", "S1": "results/unlearn/eval/S1-ifb", "T3-60": "results/unlearn/eval/T3-60-ifb", "Q5": "results/unlearn/eval/Q5"}
cc_rows = {a: [r for r in load(REPO / p / "graded.jsonl") if r["suite"] == "cotcontrol_multi" and r["level"] == 1] for a, p in CC.items()}
if_rows = {a: [r for r in load(REPO / p / "graded.jsonl") if r["suite"] == "ifbench"] for a, p in IF.items()}

cc_modes = [("end_of_sentence", "trained\n('safe')"), ("uppercase_thinking", "twin of\ncapital"), ("lowercase_thinking", "mirror of\ncapital"), ("json_format", "novel"),
            ("alternating_case", "novel"), ("repeat_sentences", "novel"), ("word_suppression", "novel"), ("multiple_word_suppression", "novel"), ("meow_between_words", "novel"), ("ignore_question", "novel,\nsemantic")]
if_cons = ["stop_words", "repeats", "conjunctions", "first_word_sent", "newline_words", "square_brackets", "emoji_end", "sentence_type_ratio", "no_consecutive_initial", "start_end_same"]

def draw(metric, ylabel, ylim, fname, note, reltop):
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 4.8), gridspec_kw={"width_ratios": [10, 10]}, sharey=True)
    arms = list(C)
    w = 0.8 / len(arms)
    ax = axes[0]
    for j, a in enumerate(arms):
        ys = [metric([r for r in cc_rows[a] if r["constraints"][0] == m], m) for m, _ in cc_modes]
        ax.bar([i + (j - 1.5) * w for i in range(len(cc_modes))], ys, width=w, color=C[a], edgecolor=SURF, label=a)
    ax.set_xticks(range(len(cc_modes))); ax.set_xticklabels([m.replace("_thinking", "").replace("_", "\n") for m, _ in cc_modes], fontsize=7.5)
    for i, (m, rel) in enumerate(cc_modes): ax.text(i, reltop, rel, ha="center", va="top", fontsize=7.5, color=MUTED)
    ax.axvline(2.5, color=MUTED, lw=1, ls=":"); ax.set_ylabel(ylabel); style(ax); ax.set_ylim(0, ylim)
    ax.set_title("CoTControl single-mode prompts (40 per mode, phase-1 run)\nleft of the dotted line: modes that restate a training constraint", loc="left", fontsize=10, color=INK)
    ax = axes[1]
    for j, a in enumerate(arms):
        ys = [metric([r for r in if_rows[a] if r["constraints"][0] == c], c) for c in if_cons]
        ax.bar([i + (j - 1.5) * w for i in range(len(if_cons))], ys, width=w, color=C[a], edgecolor=SURF)
    ax.set_xticks(range(len(if_cons))); ax.set_xticklabels([c.replace("_", "\n") for c in if_cons], fontsize=7.5); style(ax)
    for j, a in enumerate(arms): ax.bar([0], [0], color=C[a], label=a)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax.set_title("Ten never-seen constraints (IFBench-derived; 40 per constraint, both templates pooled)\nall novel; in no prompt of either phase", loc="left", fontsize=10, color=INK)
    fig.suptitle("Qwen3-8B: the same four checkpoints on the two out-of-distribution tests" + note, x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/{fname}.png", bbox_inches="tight"); plt.close(fig); 

draw(rate, "binary compliance, %", 62, "transfer_reconciliation", "", 60)
draw(cont, "continuous compliance (0–1)", 1.05, "transfer_reconciliation_continuous", " — continuous scores (ignore_question has none; word-suppression scores carry a denominator inconsistency, see REVIEW_SLACK_FINDINGS.md)", 1.02)
print("wrote figures/transfer_reconciliation.png and figures/transfer_reconciliation_continuous.png")
