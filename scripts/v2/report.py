#!/usr/bin/env python3
"""v2 gpt-oss results (V2_GPTOSS_FINDINGS.md): rule x template transfer for base, A, B, A1.

Cells per split (A's or B's train/test rules) x template group (T1-T3 seen in training, T4-T6 held out):
in-distribution, template transfer, rule transfer, rule + template transfer. Scores are macro over operations
(each operation's rules averaged first). Excluded from held-out scores: rules base passes on >= 40 % of prompts in the
same templates, and leaked rules (B: no colons, see the issues log).
"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.runs import RUN
from cotctl.v2.spec import C, role, TRAIN_TEMPLATES, HELDOUT_TEMPLATES, TEMPLATES
E = RUN["root"] / "eval"; FP = RUN["fig_prefix"]
MODELS = [m for m in ("base", "A", "B", "A1") if (E / m / "graded.jsonl").exists()]
OP = {c[2]: (c[0], c[1]) for c in C}; NAME = {c[2]: c[3] for c in C}
LEAKED = {"A": set(), "B": {"no_colons"}}
SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COL = {"base": "#c3c2b7", "A": "#2f6db5", "B": "#1f9e89", "A1": "#7fa6d6"}
# display names (internal ids A, B, A1 stay in file names, checkpoints and served model names)
DISP = {"base": "base", "A": "by-family split", "B": "within-family split", "A1": "by-family split, single template (T1)"}
SPLIT = {"A": "by-family split", "B": "within-family split"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": GRID, "font.size": 9.5, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 150, "savefig.facecolor": SURF, "xtick.color": MUTED, "ytick.color": MUTED})

G = {m: [json.loads(l) for l in open(E / m / "graded.jsonl")] for m in MODELS}
rate = {m: defaultdict(list) for m in MODELS}
for m in MODELS:
    for g in G[m]: rate[m][(g["cid"], g["template"])].append(bool(g["compliant"]))
r = lambda m, cid, tids: 100 * st.mean(x for t in tids for x in rate[m][(cid, t)]) if any(rate[m][(cid, t)] for t in tids) else None


def opmacro(m, cids, tids):
    ops = defaultdict(list)
    for c in cids:
        v = r(m, c, tids)
        if v is not None: ops[OP[c]].append(v)
    return st.mean(st.mean(v) for v in ops.values()) if ops else float("nan")


def cells(split):
    tr = [c[2] for c in C if role(c, split) == "train"]; te = [c[2] for c in C if role(c, split) == "test"]
    def clean(cids, tids): return [c for c in cids if c not in LEAKED[split] and (r("base", c, tids) or 0) < 40]
    return {"in-distribution": (tr, TRAIN_TEMPLATES), "template transfer": (tr, HELDOUT_TEMPLATES),
            "rule transfer": (clean(te, TRAIN_TEMPLATES), TRAIN_TEMPLATES), "rule + template": (clean(te, HELDOUT_TEMPLATES), HELDOUT_TEMPLATES)}


if __name__ == "__main__":
    out = {}
    for split, arms in (("A", ["base", "A", "A1"]), ("B", ["base", "B"])):
        cs = cells(split)
        for m in [x for x in arms if x in MODELS]:
            out[f"{m} on {split}'s split"] = {k: round(opmacro(m, cids, tids), 1) for k, (cids, tids) in cs.items()}
    for k, v in out.items(): print(f"{k:<20}", v)
    # accuracy, restating, truncation
    for m in MODELS:
        g = G[m]; print(m, "accuracy", round(100 * st.mean(x["correct"] for x in g), 1), "| restates rule", round(100 * st.mean(bool(x["restates"]) for x in g), 1),
                       "| truncated", round(100 * st.mean(x["truncated"] for x in g), 1), "| median words", st.median(x["words"] for x in g))
    json.dump(out, open(RUN["root"] / "summary_cells.json", "w"), indent=1)

    # Fig 1: four cells per split
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), sharey=True)
    for ax, (split, arms) in zip(axes, (("A", ["base", "A1", "A"]), ("B", ["base", "B"]))):
        ks = list(cells(split)); arms = [m for m in arms if m in MODELS]; w = 0.8 / len(arms)
        for j, m in enumerate(arms):
            ys = [out[f"{m} on {split}'s split"][k] for k in ks]; xs = [i + (j - (len(arms) - 1) / 2) * w for i in range(len(ks))]
            ax.bar(xs, ys, width=w * 0.95, color=COL[m], edgecolor=SURF, label=DISP[m])
            for x, y in zip(xs, ys): ax.text(x, (y if y == y else 0) + 1, f"{y:.0f}", ha="center", fontsize=8, color=INK2)
        ax.set_xticks(range(len(ks))); ax.set_xticklabels([f"{k}\n({'rules trained' if i < 2 else 'rules held out'}, {'T1-T3' if i % 2 == 0 else 'T4-T6'})" for i, k in enumerate(ks)], fontsize=8)
        ax.set_title(f"{SPLIT[split]}: its trained rules vs its held-out rules", loc="left", fontsize=10, color=INK)
        ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False); ax.legend(frameon=False, fontsize=8.5)
    axes[0].set_ylabel("rule satisfied, % (macro over operations)")
    fig.suptitle(f"{RUN['title']}, v2: transfer to held-out rules and held-out prompt templates", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/{FP}_cells.png", bbox_inches="tight"); plt.close(fig)

    # Fig 2: per template (held-out rules of each split)
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.2), sharey=True)
    for ax, (split, arms) in zip(axes, (("A", ["base", "A1", "A"]), ("B", ["base", "B"]))):
        te = [c[2] for c in C if role(c, split) == "test" and c[2] not in LEAKED[split]]
        tids = list(TEMPLATES)
        for m in [x for x in arms if x in MODELS]:
            ys = [opmacro(m, [c for c in te if (r("base", c, [t]) or 0) < 40], [t]) for t in tids]
            ax.plot(range(len(tids)), ys, marker="o", lw=2, color=COL[m], label=DISP[m])
        ax.axvspan(2.5, 5.5, color=GRID, alpha=0.4, lw=0); ax.text(4, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] else 1, "held-out templates", ha="center", fontsize=8, color=MUTED)
        ax.set_xticks(range(len(tids))); ax.set_xticklabels([f"{t}\n{TEMPLATES[t]['name']}" for t in tids], fontsize=7.5)
        ax.set_title(f"rules held out by the {SPLIT[split]}, by template", loc="left", fontsize=10, color=INK); ax.yaxis.grid(True, color=GRID); ax.legend(frameon=False, fontsize=8.5)
    axes[0].set_ylabel("held-out rules satisfied, %")
    fig.tight_layout(); fig.savefig(REPO / f"figures/{FP}_templates.png", bbox_inches="tight"); plt.close(fig)

    # Fig 3: every rule, every model, seen vs held-out templates (dot plot)
    fig, ax = plt.subplots(figsize=(11, 0.28 * len(C) + 1.8))
    for i, c in enumerate(C):
        ax.axhline(i, color=GRID, lw=0.5, zorder=0)
        for m in MODELS:
            for tids, mk in ((TRAIN_TEMPLATES, "o"), (HELDOUT_TEMPLATES, "^")):
                v = r(m, c[2], tids)
                if v is not None: ax.scatter(v, i, color=COL[m], marker=mk, s=26, zorder=3, edgecolor=SURF, linewidth=0.6)
    tag = lambda c: ("F" if role(c, "A") == "train" else "·") + ("W" if role(c, "B") == "train" else "·")  # trained by the by-Family / Within-family split
    ax.set_yticks(range(len(C))); ax.set_yticklabels([f"{c[3]}  {tag(c)}" for c in C], fontsize=7.2); ax.invert_yaxis(); ax.set_xlim(-3, 103)
    ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0); ax.set_xlabel("rule satisfied, % of prompts")
    from matplotlib.lines import Line2D
    hs = [Line2D([], [], color=COL[m], marker="o", lw=0, label=DISP[m]) for m in MODELS] + [Line2D([], [], color=MUTED, marker="o", lw=0, label="T1-T3"), Line2D([], [], color=MUTED, marker="^", lw=0, label="T4-T6")]
    ax.legend(handles=hs, frameon=False, fontsize=8, loc="lower right", ncol=3)
    ax.set_title("Every rule (after the name: F = trained by the by-family split, W = by the within-family split, · = held out)", loc="left", fontsize=10, color=INK)
    fig.tight_layout(); fig.savefig(REPO / f"figures/{FP}_rules.png", bbox_inches="tight"); plt.close(fig)
