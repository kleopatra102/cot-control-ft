#!/usr/bin/env python3
"""Unlearning results for one model (UNLEARNING_V2_PLAN.md): base, U, C on the operation groups of the locked split.

Scores: % of prompts whose reasoning (answer, for the "answer" condition) satisfies the rule, minus that arm's chance
rate (its own unconstrained traces; screening's for base), floored at 0, macro over operations.
Groups: trained (unlearned, headroom), held-out headroom (near / far; with and without "required word classes"),
zero-score operations. Conditions: T1, T2 (training templates), T4 (held-out template), best of 3 (T1), prefill (T1),
answer (T1).

  .venv/bin/python scripts/v2/unlearn_report.py --key qwen38_tinker
Writes results/unlearn_v2/<key>/summary.json and figures/unlearn_v2_<key>_*.png.
"""
import argparse, json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from cotctl.v2.spec import C, TRAIN_LANGS
from cotctl.v2.graders import grade, JUDGED
from cotctl.v2.build import pick_keyword

SURF, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
COL = {"base": "#c3c2b7", "C": "#7fa6d6", "U": "#d9733f"}
LAB = {"base": "base", "C": "control (C)", "U": "unlearned (U)"}
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "font.size": 9.5, "savefig.dpi": 150, "savefig.facecolor": SURF})
OP = {c[2]: (c[0], c[1]) for c in C}
RWC = ("Inclusion", "required word classes")


def chance(key, arm, th, screen_chance):
    rows = [json.loads(l) for l in open(REPO / f"results/unlearn_v2/{key}/eval/{arm}/graded.jsonl")]
    rows = [r for r in rows if r["cond"] == "calib" and r["reasoning"].strip()]
    rng = random.Random("chance"); out = {}
    for c in C:
        cid = c[2]
        if cid in JUDGED or not rows: out[cid] = screen_chance[cid]; continue
        hits = []
        for r in rows:
            a = {k: th[k] for k in "NMTW"}; a["language"] = rng.choice(TRAIN_LANGS) if cid == "given_language" else "en"
            a["keyword"] = pick_keyword(r["question"], r["reasoning"]) or "zzzz"
            hits.append(bool(grade(cid, r["reasoning"], a)))
        out[cid] = 100 * st.mean(hits)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--key", required=True); a = ap.parse_args(); key = a.key
    split = json.load(open(REPO / "data/unlearn_v2_splits.json"))[key]
    th = json.load(open(REPO / f"results/screen_v2/{key}/thresholds.json"))
    screen_chance = {c: v["chance"] for c, v in json.load(open(REPO / f"results/screen_v2/{key}/summary.json"))["rules"].items()}
    groups = {
        "trained": [(o["family"], o["operation"]) for o in split["unlearn"] if o["headroom"]],
        "unlearned half, score 0": [(o["family"], o["operation"]) for o in split["unlearn"] if not o["headroom"]],
        "held out: all headroom": [(o["family"], o["operation"]) for o in split["held_out"] if o["headroom"]],
        "held out: headroom without required word classes": [(o["family"], o["operation"]) for o in split["held_out"] if o["headroom"] and (o["family"], o["operation"]) != RWC],
        "held out: near (sibling unlearned)": [(o["family"], o["operation"]) for o in split["held_out"] if o["headroom"] and o["sibling_unlearned"]],
        "held out: far": [(o["family"], o["operation"]) for o in split["held_out"] if o["headroom"] and not o["sibling_unlearned"]],
        "held out, score 0": [(o["family"], o["operation"]) for o in split["held_out"] if not o["headroom"]],
    }
    conds = {"T1": ("grid", "T1", "s0"), "T2": ("grid", "T2", "s0"), "T4 (held-out template)": ("grid", "T4", "s0"),
             "best of 3 (T1)": ("best3", "T1", None), "prefill (T1)": ("prefill", "T1", None), "answer (T1)": ("answer", "T1", None)}
    res = {}
    for arm in ("base", "U", "C"):
        G = [json.loads(l) for l in open(REPO / f"results/unlearn_v2/{key}/eval/{arm}/graded.jsonl")]
        ch = chance(key, arm, th, screen_chance)
        cell = defaultdict(lambda: defaultdict(list))  # cond -> cid -> [bool]
        best = defaultdict(lambda: defaultdict(dict))  # (cid, sample_id) -> {k: bool}
        for g in G:
            if g["cond"] == "calib": continue
            if g["cond"] == "grid":
                cell[("grid", g["template"])][g["cid"]].append(bool(g["compliant"])) if g["k"] == 0 else None
                if g["template"] == "T1": best[g["cid"]][g["sample_id"]][g["k"]] = bool(g["compliant"])
            else: cell[(g["cond"], g["template"])][g["cid"]].append(bool(g["compliant"]))
        for cid, d in best.items():
            cell[("best3", "T1")][cid] = [any(v.values()) for v in d.values() if len(v) == 3]
        res[arm] = {"chance": ch, "accuracy": 100 * st.mean(g["correct"] for g in G if g["cond"] == "grid" and g["k"] == 0),
                    "restates": 100 * st.mean(bool(g["restates"]) for g in G if g["cond"] == "grid" and g["k"] == 0),
                    "median_words": st.median(g["words"] for g in G if g["cond"] == "grid" and g["k"] == 0), "cells": {}}
        for cname, (cond, tid, _) in conds.items():
            per = cell[(cond, tid)]
            if not per: continue
            for gname, ops in groups.items():
                vals = defaultdict(list)
                for cid, xs in per.items():
                    if OP[cid] in ops and xs:
                        sub = 0 if cond == "answer" else ch[cid]  # chance rates are for the reasoning
                        vals[OP[cid]].append(max(0.0, 100 * st.mean(xs) - sub))
                if vals: res[arm]["cells"][f"{gname} | {cname}"] = round(st.mean(st.mean(v) for v in vals.values()), 1)
    json.dump({"groups": {k: [list(o) for o in v] for k, v in groups.items()}, "arms": res}, open(REPO / f"results/unlearn_v2/{key}/summary.json", "w"), indent=1)

    gnames = list(groups); cnames = list(conds)
    print("| group | condition | base | C | U |"); print("|---|---|---:|---:|---:|")
    for gname in gnames:
        for cname in cnames:
            k = f"{gname} | {cname}"; v = [res[arm]["cells"].get(k) for arm in ("base", "C", "U")]
            if all(x is None for x in v): continue
            print(f"| {gname} | {cname} | " + " | ".join("–" if x is None else f"{x:.0f}" for x in v) + " |")
    for arm in ("base", "C", "U"):
        print(f"{arm}: accuracy {res[arm]['accuracy']:.0f} %, restates {res[arm]['restates']:.0f} %, median words {res[arm]['median_words']:.0f}")

    # figure: three main groups x conditions, base / C / U
    show = ["trained", "held out: all headroom", "held out: headroom without required word classes"]
    fig, axes = plt.subplots(1, len(show), figsize=(5.4 * len(show), 4.2), sharey=True)
    for ax, gname in zip(axes, show):
        w = 0.27
        for j, arm in enumerate(("base", "C", "U")):
            ys = [res[arm]["cells"].get(f"{gname} | {c}") for c in cnames]
            xs = [i + (j - 1) * w for i in range(len(cnames))]
            ax.bar([x for x, y in zip(xs, ys) if y is not None], [y for y in ys if y is not None], width=w * 0.92, color=COL[arm], edgecolor=SURF, label=LAB[arm])
            for x, y in zip(xs, ys):
                if y is not None: ax.text(x, y + 0.6, f"{y:.0f}", ha="center", fontsize=7.5, color=INK2)
        ax.set_xticks(range(len(cnames))); ax.set_xticklabels([c.replace(" (", "\n(") for c in cnames], fontsize=7.8, color=INK2)
        ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0, colors=MUTED)
        for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
        ax.set_title(gname.replace("held out: ", "held-out rules: "), loc="left", fontsize=9.5, color=INK)
    axes[0].set_ylabel("rule satisfied above chance, % (macro over operations)", color=INK2); axes[0].legend(frameon=False, fontsize=8.5)
    fig.suptitle(f"Unlearning CoT controllability: {key}", x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(REPO / f"figures/unlearn_v2_{key}_main.png", bbox_inches="tight"); plt.close(fig)
    print("wrote", f"figures/unlearn_v2_{key}_main.png")


if __name__ == "__main__":
    main()
