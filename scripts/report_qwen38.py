#!/usr/bin/env python3
"""Qwen3.8-27B (4-bit) base vs Q5: figures for QWEN38_FINDINGS.md. Grades stored rollouts directly (no judge; the
CoTControl ignore_question mode needs the LLM judge and is left out of the binary rates)."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.multi_eval import grade_reasonif_multi, grade_cotcontrol_multi
from cotctl.ifbench_eval import grade_ifb_rollout
from cotctl.graders.continuous import count_keyword_uses
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
C = {"base": "#c3c2b7", "Q5": "#eb6834"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "font.size": 9.5, "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF})
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
R = REPO / "results/qwen38"
MODELS = [m for m in ("base", "Q5") if (R / f"eval/{m}/rollouts.jsonl").exists()]
SUITES = [("reasonif_multi", "our six training constraints"), ("cotcontrol_multi", "CoTControl modes"), ("ifbench", "never-seen rules (10)")]

def grade_all(m):
    rs = [json.loads(l) for l in open(R / f"eval/{m}/rollouts.jsonl")]
    unc = {r["sample_id"]: count_keyword_uses(r["reasoning"] or "", r["meta"].get("keywords") or []) for r in rs if r["mode"] == "unconstrained" and r.get("think_status") == "ok"}
    out = []
    for r in rs:
        s = r["meta"]["suite"]
        if r["mode"] == "unconstrained" or r["meta"].get("level") != 1: continue
        g = grade_reasonif_multi(r) if s == "reasonif_multi" else grade_ifb_rollout(r) if s == "ifbench" else grade_cotcontrol_multi(r, {}, unc)
        c = (r["meta"].get("constraints") or r["meta"].get("modes"))[0]
        out.append({"suite": s, "c": c, "ok": r.get("think_status") == "ok", "trunc": bool(r.get("truncated")), "joint": g["joint"],
                    "cont": (g["per_continuous"] or {}).get(c), "tokens": r.get("completion_tokens", 0)})
    return out
G = {m: grade_all(m) for m in MODELS}
def rate(rows, finished_only):
    xs = [x for x in rows if x["c"] != "ignore_question" and (x["ok"] or not finished_only) and (x["joint"] is not None or not x["ok"])]
    return 100 * sum(bool(x["joint"]) for x in xs) / max(1, len(xs)), len(xs)

# Fig 1: headline per suite, all prompts and finished traces only
fig, axes = plt.subplots(1, 2, figsize=(13, 4.2), sharey=True); w = 0.38
for ax, fin, ttl in ((axes[0], False, "all prompts (cut-off traces count as failures)"), (axes[1], True, "finished traces only")):
    for j, m in enumerate(MODELS):
        ys = [rate([x for x in G[m] if x["suite"] == s], fin)[0] for s, _ in SUITES]
        ax.bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(SUITES))], ys, width=w, color=C[m], edgecolor=SURF, label=m)
        for i, y in enumerate(ys): ax.text(i + (j - (len(MODELS) - 1) / 2) * w, y + 0.8, f"{y:.0f}", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(range(len(SUITES))); ax.set_xticklabels([n for _, n in SUITES]); style(ax); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
axes[0].set_ylabel("rule satisfied, %"); axes[0].legend(frameon=False, fontsize=9, loc="upper left")
fig.suptitle("Qwen3.8-27B (4-bit): base vs Q5, single-rule prompts, identical prompts", x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / "figures/q38_headline.png", bbox_inches="tight"); plt.close(fig)

# Fig 2: per constraint / mode, binary on top and continuous below, three suites side by side
fig, axes = plt.subplots(2, 3, figsize=(18, 7.2), gridspec_kw={"width_ratios": [6, 10, 10]})
for col, (s, name) in enumerate(SUITES):
    cons = sorted({x["c"] for m in MODELS for x in G[m] if x["suite"] == s})
    for row, metric in enumerate(("binary", "cont")):
        ax = axes[row][col]
        for j, m in enumerate(MODELS):
            ys = []
            for c in cons:
                xs = [x for x in G[m] if x["suite"] == s and x["c"] == c]
                if metric == "binary": ys.append(100 * sum(bool(x["joint"]) for x in xs) / max(1, len(xs)))
                else:
                    v = [x["cont"] for x in xs if x["cont"] is not None]; ys.append(sum(v) / len(v) if v else 0)
            ax.bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(cons))], ys, width=w, color=C[m], edgecolor=SURF, label=m)
        ax.set_xticks(range(len(cons))); ax.set_xticklabels([c.replace("_thinking", "").replace("_", "\n") for c in cons], fontsize=7)
        style(ax); ax.set_ylim(0, 105 if metric == "binary" else 1.05)
        if row == 0: ax.set_title(name, loc="left", fontsize=10, color=INK)
        if col == 0: ax.set_ylabel("binary, % of all prompts" if metric == "binary" else "continuous (0–1)")
axes[0][0].legend(frameon=False, fontsize=9, loc="upper left")
fig.suptitle("Qwen3.8-27B: each rule, binary (top) and continuous (bottom); 20 prompts per rule", x=0.01, ha="left", fontsize=11, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(REPO / "figures/q38_per_rule.png", bbox_inches="tight"); plt.close(fig)

# Fig 3: trace length and truncation
fig, axes = plt.subplots(1, 2, figsize=(13, 3.8))
for j, m in enumerate(MODELS):
    t = [100 * sum(x["trunc"] for x in G[m] if x["suite"] == s) / max(1, sum(1 for x in G[m] if x["suite"] == s)) for s, _ in SUITES]
    md = [st.median([x["tokens"] for x in G[m] if x["suite"] == s] or [0]) for s, _ in SUITES]
    axes[0].bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(SUITES))], md, width=w, color=C[m], edgecolor=SURF, label=m)
    axes[1].bar([i + (j - (len(MODELS) - 1) / 2) * w for i in range(len(SUITES))], t, width=w, color=C[m], edgecolor=SURF)
for ax, ttl in zip(axes, ("median completion tokens", "cut off at the 12,288-token cap, %")):
    ax.set_xticks(range(len(SUITES))); ax.set_xticklabels([n for _, n in SUITES]); style(ax); ax.set_title(ttl, loc="left", fontsize=10, color=INK)
axes[0].legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(REPO / "figures/q38_length_truncation.png", bbox_inches="tight"); plt.close(fig)

# Fig 4: Redwood's nine held-out instructions
RW = {m: json.load(open(R / f"redwood/{m}/summary.json")) for m in MODELS if (R / f"redwood/{m}/summary.json").exists()}
if RW:
    ins = [k for k in next(iter(RW.values())) if not k.startswith("_")]
    fig, ax = plt.subplots(figsize=(12, 3.8))
    for j, m in enumerate(RW):
        ys = [100 * RW[m][k]["raw_compliance"] for k in ins]
        ax.bar([i + (j - (len(RW) - 1) / 2) * w for i in range(len(ins))], ys, width=w, color=C[m], edgecolor=SURF, label=m)
        for i, y in enumerate(ys): ax.text(i + (j - (len(RW) - 1) / 2) * w, y + 1, f"{y:.0f}", ha="center", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(ins))); ax.set_xticklabels([k.replace("_", "\n") for k in ins], fontsize=8); ax.set_ylabel("raw compliance, %"); style(ax); ax.set_ylim(0, 105)
    ax.legend(frameon=False, fontsize=9, loc="upper left"); ax.set_title("Redwood's nine held-out instructions (about 30 tasks each)", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(REPO / "figures/q38_redwood.png", bbox_inches="tight"); plt.close(fig)
for m in MODELS:
    print(m, {s: (round(rate([x for x in G[m] if x["suite"] == s], False)[0], 1), round(rate([x for x in G[m] if x["suite"] == s], True)[0], 1)) for s, _ in SUITES},
          "trunc", {s: sum(x["trunc"] for x in G[m] if x["suite"] == s) for s, _ in SUITES})
print("redwood:", {m: round(100 * RW[m]["_macro"], 1) for m in RW})
