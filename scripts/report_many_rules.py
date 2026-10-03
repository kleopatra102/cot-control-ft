#!/usr/bin/env python3
"""Many-rule arms A and B against base and Q5 on Qwen3.8-27B (MANY_RULES_PLAN.md): figures for MANY_RULES_FINDINGS.md.
Every evaluated condition is scored per model (share of prompts satisfying the rule; cut-off traces count as failures)
and labelled trained / held-out per arm. ignore_question (needs the judge) is left out."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.multi_eval import grade_reasonif_multi, grade_cotcontrol_multi
from cotctl.ifbench_eval import grade_ifb_rollout
from cotctl.graders.continuous import count_keyword_uses
from cotctl.sft import pool as P
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
C = {"base": "#c3c2b7", "Q5": "#eb6834", "A": "#2f6db5", "B": "#1f9e89"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def style(ax, axis="y"): (ax.yaxis if axis == "y" else ax.xaxis).grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0)
SET = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--set=")), "qwen38")
_G, _GM, _RW, _R1 = REPO / "results/gptoss", REPO / "results/gptoss_many", REPO / "results/redwood_eval", REPO / "results/r1llama"
Q, R = REPO / "results/qwen38", REPO / "results/qwen38_many"
EVAL, RWD, FIG, TITLE = {
    "qwen38": ({"base": Q / "eval/base", "Q5": Q / "eval/Q5", "A": R / "eval/A", "B": R / "eval/B"},
               {"base": Q / "redwood/base", "Q5": Q / "redwood/Q5", "A": R / "redwood/A", "B": R / "redwood/B"}, "many", "Qwen3.8-27B"),
    "gptoss": ({"base": _G / "eval/base", "Q5": _G / "eval/Q5-final", "A": _GM / "eval/A", "B": _GM / "eval/B"},
               {"base": _RW / "base", "Q5": _RW / "Q5-final", "A": _GM / "redwood/A", "B": _GM / "redwood/B"}, "many_gptoss", "gpt-oss-20b"),
    "r1": ({m: _R1 / f"eval/{m}" for m in ("base", "Q5", "A", "B")}, {m: _R1 / f"redwood/{m}" for m in ("base", "Q5", "A", "B")}, "many_r1", "R1-Distill-Llama-8B"),
}[SET]
MODELS = [m for m in EVAL if (EVAL[m] / "rollouts.jsonl").exists()]
PREFIX = {"reasonif_multi": "rif", "cotcontrol_multi": "cc", "ifbench": "ifb"}
Q5_TRAINED = {f"rif:{c}" for c in ("capital", "end_checker", "end_of_sentence", "no_comma", "number_words", "reasoning_language")} | {"cc:end_of_sentence"}  # + its CoTControl twin
BASE_HIGH = None  # set below: conditions base already passes on >= 40 % of prompts (no room to show transfer)


def scores(m):
    """{condition id: [bool per prompt]}"""
    out = defaultdict(list)
    rs = [json.loads(l) for l in open(EVAL[m] / "rollouts.jsonl")]
    unc = {r["sample_id"]: count_keyword_uses(r["reasoning"] or "", r["meta"].get("keywords") or []) for r in rs if r["mode"] == "unconstrained" and r.get("think_status") == "ok"}
    for r in rs:
        s = r["meta"]["suite"]
        if r["mode"] == "unconstrained" or r["meta"].get("level") != 1: continue
        c = (r["meta"].get("constraints") or r["meta"].get("modes"))[0]
        if c == "ignore_question": continue
        g = grade_reasonif_multi(r) if s == "reasonif_multi" else grade_ifb_rollout(r) if s == "ifbench" else grade_cotcontrol_multi(r, {}, unc)
        out[f"{PREFIX[s]}:{c}"].append(bool(g["joint"]))
    if (RWD[m] / "graded.jsonl").exists():
        for l in open(RWD[m] / "graded.jsonl"):
            g = json.loads(l); out[f"rw:{g['instruction']}"].append(bool(g["compliant"]))
    return out


S = {m: scores(m) for m in MODELS}
rate = lambda m, c: 100 * sum(S[m][c]) / len(S[m][c]) if S[m].get(c) else None
TRAIN = {arm: set(P.split(arm)[0]) for arm in "AB"}; TEST = {arm: set(P.split(arm)[1]) for arm in "AB"}
EVALUATED = sorted(c for c in set.intersection(*[set(S[m]) for m in MODELS]) if c in P.CONDS)
BASE_HIGH = {c for c in EVALUATED if rate("base", c) >= 40}
# held-out sets used for headline numbers: evaluated, not trained by Q5 either, base not already high
# Held-out conditions that training reaches without the rule being trained (CONDITION_SPLIT.md, "Overlaps and leakage"):
# B's rewrites thin stop words and cap length, so 96 % of B's English training traces lack "so" and 63 % lack "the";
# B's "hence"-insertion puts a fixed word at sentence starts ("Indeed"); A's length training satisfies "no word > 10 times".
CONTAMINATED = {"A": {"ifb:repeats", "ifb:stop_words"},
                "B": {"cc:word_suppression", "cc:multiple_word_suppression", "rw:no_the", "rw:no_answer_word", "rw:no_word_so", "ifb:first_word_sent"}}
HELD = {arm: [c for c in EVALUATED if c in TEST[arm] and c not in Q5_TRAINED and c not in BASE_HIGH and c not in CONTAMINATED[arm]] for arm in "AB"}
CORE = [c for c in EVALUATED if c in P.SHARED_CORE]


def micro(m, conds): xs = [v for c in conds for v in S[m][c]]; return 100 * sum(xs) / max(1, len(xs))
def macro(m, conds): return st.mean(rate(m, c) for c in conds) if conds else 0
def opmacro(m, conds):
    """Headline metric: average within each operation first, so reworded variants of one rule count once."""
    ops = defaultdict(list)
    for c in conds: ops[P.CONDS[c].op].append(rate(m, c))
    return st.mean(st.mean(v) for v in ops.values()) if ops else 0
def n_ops(conds): return len({P.CONDS[c].op for c in conds})


if __name__ == "__main__":
    for arm in "AB": print(arm, "held-out:", HELD[arm])
    print("core:", CORE)
    for m in MODELS:
        print(m, "per-op", {f"{arm}-test": round(opmacro(m, HELD[arm]), 1) for arm in "AB"}, "core", round(opmacro(m, CORE), 1), "| per-cond", {f"{arm}-test": round(macro(m, HELD[arm]), 1) for arm in "AB"}, "core", round(macro(m, CORE), 1),
              {f"{arm}-train": round(macro(m, [c for c in EVALUATED if c in TRAIN[arm]]), 1) for arm in "AB"})
    NAME = {"base": "base", "Q5": "Q5 (6 rules)", "A": "A (family split)", "B": "B (within-family split)"}
    groups = [("shared core\n(held out in both arms)", CORE, MODELS), ("A's held-out\nconditions", HELD["A"], ["base", "Q5", "A"]),
              ("B's held-out\nconditions", HELD["B"], ["base", "Q5", "B"])]
    # Fig 1: headline, each arm only on conditions it never trained
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), sharey=True)
    for ax, fn, ttl in ((axes[0], opmacro, "macro over operations (headline: reworded variants count once)"), (axes[1], macro, "macro over conditions")):
        x = 0; ticks = []
        for name, conds, ms in groups:
            for j, m in enumerate(ms):
                y = fn(m, conds); ax.bar(x + j * 0.8, y, width=0.76, color=C[m], edgecolor=SURF, label=NAME[m] if name.startswith("shared") else None)
                ax.text(x + j * 0.8, y + 0.8, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
            ticks.append((x + (len(ms) - 1) * 0.4, f"{name}\n({n_ops(conds)} operations, {len(conds)} conditions)")); x += len(ms) * 0.8 + 1.0
        ax.set_xticks([t for t, _ in ticks]); ax.set_xticklabels([l for _, l in ticks], fontsize=8.5); style(ax); ax.spines["left"].set_visible(False)
        ax.set_title(ttl, loc="left", fontsize=10, color=INK)
    axes[0].set_ylabel("rule satisfied, %"); h, l = axes[0].get_legend_handles_labels(); fig.legend(h, l, frameon=False, fontsize=8.5, loc="upper right", ncol=4, bbox_to_anchor=(1.0, 0.95))
    fig.suptitle(f"{TITLE}: held-out conditions only (never trained by the model shown nor by Q5; leaked conditions removed)", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/{FIG}_headline.png", bbox_inches="tight"); plt.close(fig)
    # Fig 3: A against B per condition, coloured by who trained it
    fig, ax = plt.subplots(figsize=(7.2, 6.4))
    kinds = {"trained by A only": ("#2f6db5", "o"), "trained by B only": ("#1f9e89", "s"), "trained by both": ("#52514e", "D"), "held out in both": ("#eb6834", "^")}
    for c in EVALUATED:
        k = "trained by both" if c in TRAIN["A"] and c in TRAIN["B"] else "trained by A only" if c in TRAIN["A"] else "trained by B only" if c in TRAIN["B"] else "held out in both"
        ax.scatter(rate("A", c), rate("B", c), color=kinds[k][0], marker=kinds[k][1], s=48, edgecolor=SURF, linewidth=1, zorder=3)
    for k, (col, mk) in kinds.items(): ax.scatter([], [], color=col, marker=mk, s=48, label=k)
    for c in EVALUATED:
        a_, b_ = rate("A", c), rate("B", c)
        if abs(a_ - b_) >= 15 or max(a_, b_) >= 60: ax.annotate(c.split(":", 1)[1].replace("_", " "), (a_, b_), xytext=(4, 3), textcoords="offset points", fontsize=7, color=INK2)
    ax.plot([0, 100], [0, 100], color=GRID, lw=1, zorder=1); ax.set_xlim(-3, 103); ax.set_ylim(-3, 103); ax.set_aspect("equal")
    ax.set_xlabel("arm A, % of prompts"); ax.set_ylabel("arm B, % of prompts"); style(ax); style(ax, "x"); ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Each condition: A against B. Off-diagonal points are\nwhere training on the rule made a difference", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(REPO / f"figures/{FIG}_a_vs_b.png", bbox_inches="tight"); plt.close(fig)
    # Fig 4: accuracy and length on Redwood's tasks
    acc, words = {}, {}
    for m in MODELS:
        g = [json.loads(l) for l in open(RWD[m] / "graded.jsonl")]; acc[m] = 100 * sum(bool(x["correct"]) for x in g) / len(g); words[m] = st.median(x["words"] for x in g)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
    for ax, d, ttl, fmt in ((axes[0], acc, "answer accuracy on Redwood's tasks, %", "{:.0f}"), (axes[1], words, "median reasoning length, words", "{:.0f}")):
        ax.bar(range(len(MODELS)), [d[m] for m in MODELS], color=[C[m] for m in MODELS], edgecolor=SURF, width=0.6)
        for i, m in enumerate(MODELS): ax.text(i, d[m] * 1.01 + 0.5, fmt.format(d[m]), ha="center", fontsize=8.5, color=INK2)
        ax.set_xticks(range(len(MODELS))); ax.set_xticklabels([NAME[m] for m in MODELS], fontsize=8.5); style(ax); ax.spines["left"].set_visible(False); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(REPO / f"figures/{FIG}_accuracy_length.png", bbox_inches="tight"); plt.close(fig)
    # Fig 2: every evaluated condition, dot plot, grouped by family
    fam_order = ["case", "bans", "inclusion", "position", "layout", "structure", "style", "statistics", "length", "language"]
    conds = sorted(EVALUATED, key=lambda c: (fam_order.index(P.CONDS[c].family), P.CONDS[c].op, c))
    fig, ax = plt.subplots(figsize=(10, 0.27 * len(conds) + 1.5))
    for i, c in enumerate(conds):
        ax.axhline(i, color=GRID, lw=0.6, zorder=0)
        for m in MODELS:
            ax.scatter(rate(m, c), i, s=34, color=C[m], edgecolor=SURF, linewidth=1, zorder=3 if m in "AB" else 2, label=m if i == 0 else None)
    lab = [f"{c.split(':', 1)[1].replace('_', ' ')}  ({c.split(':')[0]})  " + ("A" if c in TRAIN["A"] else "·") + ("B" if c in TRAIN["B"] else "·") for c in conds]
    ax.set_yticks(range(len(conds))); ax.set_yticklabels(lab, fontsize=7.5); ax.invert_yaxis(); ax.set_xlim(-3, 103); style(ax, "x")
    ax.set_xlabel("rule satisfied, % of prompts"); ax.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=4)
    ax.set_title("Every condition; trailing letters mark which arm trained it (A, B, or · for held out)", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(REPO / f"figures/{FIG}_per_condition.png", bbox_inches="tight"); plt.close(fig)
