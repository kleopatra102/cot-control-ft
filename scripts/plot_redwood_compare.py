#!/usr/bin/env python3
"""Figures for REDWOOD_GPTOSS_ANALYSIS.md: our gpt-oss checkpoints on Redwood's nine held-out instructions next to
their fine-tune, and the same checkpoints across the three out-of-distribution test sets."""
import json, re, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.ifbench_eval import ALL
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
L = ["base", "R-final", "S1-final", "T3-60", "T3-final", "Q5-final"]
NAME = {"base": "base", "R-final": "R (control)", "S1-final": "S1", "T3-60": "T3 step-60", "T3-final": "T3", "Q5-final": "Q5"}
C = {"base": "#c3c2b7", "R-final": "#7d7a6f", "S1-final": "#86b6ef", "T3-60": "#5a8fd0", "T3-final": "#104281", "Q5-final": "#eb6834", "RW": "#2e9e6b"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
RW = {l: json.load(open(REPO / f"results/redwood_eval/{l}/summary.json")) for l in L}
THEIRS = {"bullet": 57, "terse_25w": 61, "numbered": 9, "section_headers": 0, "no_word_so": 3, "include_exactly_twice": 0, "xml_steps": 0, "child_explanation": 0, "initial_caps": 0}
ORDER = list(THEIRS)
REL = {"bullet": "novel\n(native answer format)", "terse_25w": "twin of trained\nword budget", "numbered": "novel\n(native answer format)", "section_headers": "novel", "no_word_so": "novel", "include_exactly_twice": "novel",
       "xml_steps": "novel", "child_explanation": "novel", "initial_caps": "novel"}

# Fig A: per instruction, our six checkpoints + Redwood's fine-tune
fig, ax = plt.subplots(figsize=(14, 4.8)); w = 0.8 / 7
for j, l in enumerate(L):
    ax.bar([i + (j - 3) * w for i in range(len(ORDER))], [100 * RW[l][k]["raw_compliance"] for k in ORDER], width=w, color=C[l], edgecolor=SURF, label=NAME[l])
ax.bar([i + 3 * w for i in range(len(ORDER))], [THEIRS[k] for k in ORDER], width=w, color=C["RW"], edgecolor=SURF, hatch="//", label="Redwood fine-tune")
for i, k in enumerate(ORDER): ax.text(i, 101, REL[k], ha="center", va="bottom", fontsize=7, color=MUTED)
ax.set_xticks(range(len(ORDER))); ax.set_xticklabels([k.replace("_", "\n") for k in ORDER], fontsize=8.5); ax.set_ylim(0, 112); ax.set_ylabel("raw compliance, %"); style(ax)
ax.legend(frameon=False, fontsize=8.5, ncol=7, loc="upper center", bbox_to_anchor=(0.5, -0.14))
ax.set_title("gpt-oss-20b on Redwood's nine held-out instructions: our checkpoints (solid) and Redwood's own fine-tune (hatched)\n100 held-out tasks each, their prompts and scorers, greedy decoding", loc="left", fontsize=10.5, color=INK, pad=28)
fig.tight_layout(); fig.savefig(REPO / "figures/redwood_heldout_ours_vs_theirs.png", bbox_inches="tight"); plt.close(fig)

# Fig B: the same checkpoints on the three out-of-distribution test sets
G = {l: [json.loads(x) for x in open(REPO / f"results/gptoss/eval/{l}/graded.jsonl")] for l in L}
RO = {l: {(r["sample_id"], r["mode"]): r for r in (json.loads(x) for x in open(REPO / f"results/gptoss/eval/{l}/rollouts.jsonl"))} for l in L}
def restates(r):
    t = (r.get("reasoning") or "").lower(); c = r["meta"]["constraints"][0]
    ins = ALL[c]["rif" if r["meta"]["template"] == "rif" else "cc"].lower(); words = re.findall(r"[a-z]{5,}", ins)[:12]
    return sum(w in t for w in words) >= max(3, int(0.6 * len(words))) or "the user said" in t or "rules:" in t or "requirement" in t
def rate(rows):
    v = [r["joint"] for r in rows if r["think_status"] == "ok" and r["joint"] is not None]; return 100 * sum(v) / max(1, len(v))
NOVEL_CC = ["json_format", "lowercase_thinking", "alternating_case", "repeat_sentences", "word_suppression", "multiple_word_suppression", "meow_between_words", "ignore_question"]
sets = [("CoTControl, novel modes (8)\ntheir template", lambda l: rate([r for r in G[l] if r["suite"] == "cotcontrol_multi" and r["level"] == 1 and r["constraints"][0] in NOVEL_CC])),
        ("our never-seen rules (30)\ntraces not restating the rule", lambda l: rate([g for g in G[l] if g["suite"] == "ifbench" and not restates(RO[l][(g["sample_id"], g["mode"])])])),
        ("Redwood held-out (9)\nexcluding the word-budget twin", lambda l: 100 * sum(RW[l][k]["raw_compliance"] for k in ORDER if k != "terse_25w") / 8),
        ("Redwood: bullet + numbered\n(native answer formats)", lambda l: 100 * (RW[l]["bullet"]["raw_compliance"] + RW[l]["numbered"]["raw_compliance"]) / 2)]
fig, ax = plt.subplots(figsize=(12, 4.6)); w = 0.8 / len(L)
for j, l in enumerate(L):
    ys = [f(l) for _, f in sets]
    ax.bar([i + (j - 2.5) * w for i in range(len(sets))], ys, width=w, color=C[l], edgecolor=SURF, label=NAME[l])
    for i, y in enumerate(ys): ax.text(i + (j - 2.5) * w, y + 0.8, f"{y:.0f}", ha="center", fontsize=7, color=INK2)
ax.set_xticks(range(len(sets))); ax.set_xticklabels([s for s, _ in sets], fontsize=8.5); ax.set_ylabel("compliance, %"); style(ax)
ax.legend(frameon=False, fontsize=8.5, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.2))
ax.set_title("Same gpt-oss-20b checkpoints, three out-of-distribution test sets: transfer appears only where the test contains formats the model already writes in answers", loc="left", fontsize=10.5, color=INK)
fig.tight_layout(); fig.savefig(REPO / "figures/redwood_vs_our_tests.png", bbox_inches="tight"); plt.close(fig)
print("wrote figures/redwood_heldout_ours_vs_theirs.png, figures/redwood_vs_our_tests.png")

# Fig C: across models, the one novel format that relocates from the answer into the reasoning, vs the other novel rules
def q8(l, modes):
    rows = [json.loads(x) for x in open(REPO / f"results/qwen3_8b/eval/{l}/graded.jsonl")]
    rows = [r for r in rows if r["suite"] == "cotcontrol_multi" and r["level"] == 1 and r["constraints"][0] in modes and r["think_status"] == "ok"]
    v = [r["per_binary"][r["constraints"][0]] for r in rows if r["per_binary"].get(r["constraints"][0]) is not None]; return 100 * sum(v) / max(1, len(v))
OTHER_Q8 = ["alternating_case", "repeat_sentences", "word_suppression", "multiple_word_suppression", "meow_between_words", "ignore_question"]
arms = [("base", "base", "base"), ("S1", "S1-final", "S1-final"), ("T3 step-60", "T3-60", "T3-60"), ("Q5", "Q5-final", "Q5-final")]
panels = [("Qwen3-8B: JSON in the reasoning\n(CoTControl; base writes JSON in its answer)", [q8(a[1], ["json_format"]) for a in arms]),
          ("Qwen3-8B: other novel CoTControl modes (6)", [q8(a[1], OTHER_Q8) for a in arms]),
          ("gpt-oss-20b: bullet list in the reasoning\n(Redwood suite; base formats its answer this way when asked)", [100 * RW[a[2]]["bullet"]["raw_compliance"] for a in arms]),
          ("gpt-oss-20b: other novel Redwood rules (7)", [100 * sum(RW[a[2]][k]["raw_compliance"] for k in ORDER if k not in ("bullet", "terse_25w")) / 7 for a in arms])]
fig, axes = plt.subplots(1, 4, figsize=(15, 3.8), sharey=True)
cols = [C["base"], C["S1-final"], C["T3-60"], C["Q5-final"]]
for ax, (ttl, ys) in zip(axes, panels):
    ax.bar(range(len(arms)), ys, color=cols, edgecolor=SURF, width=0.65)
    for i, y in enumerate(ys): ax.text(i, y + 1, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(arms))); ax.set_xticklabels([a[0] for a in arms], fontsize=8.5); ax.set_title(ttl, loc="left", fontsize=9.5, color=INK); style(ax)
axes[0].set_ylabel("compliance, %"); axes[0].set_ylim(0, 90)
fig.suptitle("Two models, the same pattern: the novel format that transfers is one the base model already writes in its answers; other novel rules barely move", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.9)); fig.savefig(REPO / "figures/redwood_cross_model_pattern.png", bbox_inches="tight"); plt.close(fig)
print("wrote figures/redwood_cross_model_pattern.png")
