#!/usr/bin/env python3
"""gpt-oss-20b multi-constraint run: figure figures/gptoss_overview.png (GPTOSS_FINDINGS.md)."""
import json, re, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.ifbench_eval import ALL
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
L = ["base", "R-final", "S1-final", "T3-60", "T3-final", "Q5-final"]
C = {"base": "#c3c2b7", "R-final": "#7d7a6f", "S1-final": "#86b6ef", "T3-60": "#5a8fd0", "T3-final": "#104281", "Q5-final": "#eb6834"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
G = {l: [json.loads(x) for x in open(REPO / f"results/gptoss/eval/{l}/graded.jsonl")] for l in L}
RO = {l: {(r["sample_id"], r["mode"]): r for r in (json.loads(x) for x in open(REPO / f"results/gptoss/eval/{l}/rollouts.jsonl"))} for l in L}
def rate(rs, c):
    v = [r["per_binary"][c] for r in rs if r["think_status"] == "ok" and r["per_binary"].get(c) is not None]; return 100 * sum(v) / len(v) if v else 0
def restates(r):
    t = (r.get("reasoning") or "").lower(); c = r["meta"]["constraints"][0]
    ins = ALL[c]["rif" if r["meta"]["template"] == "rif" else "cc"].lower(); words = re.findall(r"[a-z]{5,}", ins)[:12]
    return sum(w in t for w in words) >= max(3, int(0.6 * len(words))) or "the user said" in t or "rules:" in t or "requirement" in t
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
fig, axes = plt.subplots(1, 3, figsize=(19, 4.8), gridspec_kw={"width_ratios": [6, 10, 3.2]})
w = 0.8 / len(L)
rif_c = ["reasoning_language", "number_words", "capital", "no_comma", "end_checker", "end_of_sentence"]
cc_m = ["end_of_sentence", "uppercase_thinking", "lowercase_thinking", "json_format", "repeat_sentences", "word_suppression", "multiple_word_suppression", "alternating_case", "meow_between_words", "ignore_question"]
for ax, suite, items, ttl in ((axes[0], "reasonif_multi", rif_c, "ReasonIF single constraints (in-domain; 20 each)"), (axes[1], "cotcontrol_multi", cc_m, "CoTControl single modes (transfer; 40 each)")):
    for j, l in enumerate(L):
        ys = [rate([r for r in G[l] if r["suite"] == suite and r["level"] == 1 and r["constraints"][0] == c], c) for c in items]
        ax.bar([i + (j - (len(L) - 1) / 2) * w for i in range(len(items))], ys, width=w, color=C[l], edgecolor=SURF, label=l)
    ax.set_xticks(range(len(items))); ax.set_xticklabels([c.replace("_thinking", "").replace("_", "\n") for c in items], fontsize=7.5); style(ax); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
axes[0].set_ylabel("binary compliance, %"); axes[0].legend(frameon=False, fontsize=8, loc="upper right")
ax = axes[2]
for j, l in enumerate(L):
    ys = []
    for want in (True, False):
        rs = [g for g in G[l] if g["suite"] == "ifbench" and g["think_status"] == "ok" and g["joint"] is not None and restates(RO[l][(g["sample_id"], g["mode"])]) == want]
        ys.append(100 * sum(g["joint"] for g in rs) / max(1, len(rs)))
    ax.bar([0 + (j - 2.5) * w, 1 + (j - 2.5) * w], ys, width=w, color=C[l], edgecolor=SURF)
ax.set_xticks([0, 1]); ax.set_xticklabels(["trace restates\nthe rule", "trace does not\nrestate the rule"], fontsize=8.5); style(ax)
ax.set_title("Thirty never-seen rules, pooled\n(both templates)", loc="left", fontsize=10, color=INK)
fig.suptitle("gpt-oss-20b: multi-constraint SFT teaches the trained rules and does not transfer (R = matched-reasoning control)", x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / "figures/gptoss_overview.png", bbox_inches="tight"); print("wrote figures/gptoss_overview.png")
