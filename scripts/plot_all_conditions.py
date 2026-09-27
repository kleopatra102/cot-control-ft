#!/usr/bin/env python3
"""All 40 out-of-distribution conditions in one figure: 10 CoTControl modes, 10 never-seen (batch 1), 20 never-seen
(batch 2). Binary on top, continuous below; relation to the training set labelled per condition.
Writes figures/all_conditions_best_template.png."""
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
def load(p): return [json.loads(l) for l in open(REPO / p / "graded.jsonl")]
def rows_of(rs, c, tpl=None): return [r for r in rs if r["constraints"][0] == c and r["think_status"] == "ok" and (tpl is None or r["mode"].endswith(":" + tpl))]
def rate(rs, c):
    v = [r["per_binary"][c] for r in rs if r["per_binary"].get(c) is not None]; return (100 * sum(v) / len(v)) if v else None
def cont(rs, c):
    v = [r["per_continuous"][c] for r in rs if r["per_continuous"].get(c) is not None]; return (sum(v) / len(v)) if v else None

cc = {a: [r for r in load(p) if r["suite"] == "cotcontrol_multi" and r["level"] == 1] for a, p in
      {"base": "results/qwen3_8b/eval/base", "S1": "results/qwen3_8b/eval/S1-final", "T3-60": "results/qwen3_8b/eval/T3-60", "Q5": "results/qwen3_8b/eval/Q5-final"}.items()}
b1 = {a: [r for r in load(p) if r["suite"] == "ifbench"] for a, p in
      {"base": "results/unlearn/eval/base", "S1": "results/unlearn/eval/S1-ifb", "T3-60": "results/unlearn/eval/T3-60-ifb", "Q5": "results/unlearn/eval/Q5"}.items()}
b2 = {a: [r for r in load(p) if r["suite"] == "ifbench"] for a, p in {"base": "results/unlearn/eval/base-ifb2", "Q5": "results/unlearn/eval/Q5-ifb2"}.items()}

conds = [(cc, m, rel) for m, rel in [("end_of_sentence", "identical\n('safe')"), ("uppercase_thinking", "twin of\ncapital"), ("lowercase_thinking", "mirror of\ncapital"),
         ("json_format", "novel"), ("alternating_case", "novel"), ("repeat_sentences", "novel"), ("word_suppression", "novel"), ("multiple_word_suppression", "novel"),
         ("meow_between_words", "novel"), ("ignore_question", "novel,\nsemantic")]]
conds += [(b1, c, "novel") for c in ["stop_words", "repeats", "conjunctions", "first_word_sent", "newline_words", "square_brackets", "emoji_end", "sentence_type_ratio", "no_consecutive_initial", "start_end_same"]]
conds += [(b2, c, "novel") for c in ["quotes_nested", "palindromes", "parentheses_nested", "numbers_exact", "punctuation_all", "single_vowel", "keyword_nth_sentence", "no_whitespace", "sentence_hyphens", "line_indent",
          "bigram_wrapping", "sentence_increment", "last_first", "alliteration_increment", "no_adjacent_consec", "prime_lengths", "consonant_cluster", "odd_even_syllables", "words_position", "paragraph_last_first"]]
groups = [(0, 10, "CoTControl modes (40 prompts each)"), (10, 20, "never-seen, batch 1 (IFBench-derived; 20 each, better template per rule)"), (20, 40, "never-seen, batch 2 (base and Q5 only; 20 each, better template per rule)")]
arms = list(C); w = 0.8 / len(arms)
# best template per never-seen rule: higher mean binary across the arms evaluated on it (tie -> continuous);
# chosen once per rule and applied to every arm, so the arm comparison is not biased toward any arm
BEST = {}
for src, c, rel in conds:
    if src is cc: continue
    def score(t):
        b = [rate(rows_of(src[a], c, t), c) or 0 for a in src]; k = [cont(rows_of(src[a], c, t), c) or 0 for a in src]
        return (sum(b) / len(b), sum(k) / len(k))
    BEST[c] = max(("rif", "cc"), key=score)
TPL = {c: BEST.get(c) for _, c, _ in conds}
print({c: t for c, t in BEST.items()})

fig, axes = plt.subplots(2, 1, figsize=(26, 8.8), sharex=True)
for ax, metric, ylabel, ylim, reltop in ((axes[0], rate, "binary compliance, %", 70, 68), (axes[1], cont, "continuous compliance (0–1)", 1.12, None)):
    for j, a in enumerate(arms):
        xs, ys = [], []
        for i, (src, c, rel) in enumerate(conds):
            if a not in src: continue
            v = metric(rows_of(src[a], c, TPL[c]), c)
            if v is not None:
                present = [x for x in arms if x in src]; k = present.index(a)
                xs.append(i + (k - (len(present) - 1) / 2) * w); ys.append(v)
        ax.bar(xs, ys, width=w, color=C[a], edgecolor=SURF, label=a)
    for lo, hi, name in groups[1:]: ax.axvline(lo - 0.5, color=MUTED, lw=1)
    ax.axvline(2.5, color=MUTED, lw=1, ls=":")
    ax.set_ylabel(ylabel); ax.set_ylim(0, ylim); ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
    if reltop:
        for i, (src, c, rel) in enumerate(conds):
            ax.text(i, reltop, rel + ("" if src is cc else "\n" + {"rif": "R", "cc": "C"}[TPL[c]]), ha="center", va="top", fontsize=7, color=INK2 if rel != "novel" else MUTED, fontweight="bold" if rel != "novel" else "normal")
        for lo, hi, name in groups: ax.text((lo + hi - 1) / 2, ylim + 3, name, ha="center", va="bottom", fontsize=9.5, color=INK)
axes[0].legend(frameon=False, fontsize=9, loc="upper right", bbox_to_anchor=(1.0, 0.86))
axes[1].set_xticks(range(len(conds))); axes[1].set_xticklabels([c.replace("_thinking", "").replace("_", "\n") for _, c, _ in conds], fontsize=7)
axes[1].text(19.5, -0.42, "Never-seen rules: R = ReasonIF \"rules\" template, C = CoTControl \"Requirement\" template; the one with the higher mean binary rate across arms, chosen per rule and used for every arm. CoTControl modes exist only in their own template. S1 and T3-60 not evaluated on batch 2; ignore_question has no continuous score.", ha="center", fontsize=8, color=MUTED)
fig.suptitle("Qwen3-8B: every out-of-distribution condition, binary (top) and continuous (bottom).  Left of the dotted line: CoTControl modes that restate a training constraint; everything else is novel.",
             x=0.01, ha="left", fontsize=11.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(REPO / "figures/all_conditions_best_template.png", bbox_inches="tight"); print("wrote figures/all_conditions_best_template.png")
