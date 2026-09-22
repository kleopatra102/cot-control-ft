#!/usr/bin/env python3
"""Paired per-mode analysis of S2 (layer 16, coef -7 vs 0, all nine modes). Reads results/steer/steered_eval_base_s2.json.
Writes results/steer/s2_paired.json, figures/steer_s2_paired.png and prints the table."""
from __future__ import annotations
import json, random, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
REPO = Path(__file__).resolve().parents[2]
SURF, INK, INK2, MUTED, GRID, BASE, BLUE, LIGHT, ORANGE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#2a78d6", "#86b6ef", "#eb6834"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": BASE, "axes.facecolor": SURF, "figure.facecolor": SURF, "savefig.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})
MODES = ["uppercase_thinking", "lowercase_thinking", "alternating_case", "word_suppression", "multiple_word_suppression", "repeat_sentences", "end_of_sentence", "meow_between_words", "ignore_question"]
E = json.load(open(REPO / "results/steer/steered_eval_base_s2.json")); rows = [r for r in E["rows"] if r["ok"]]
by = {(r["coef"], r["mode"], r["sample_id"]): r for r in rows}
def dens(r): return 1000 * r["llm_n_sent"] / r["reasoning_words"] if r.get("llm_n_sent") is not None and r["reasoning_words"] > 0 else None
def boot(pairs, n=4000, seed=0):
    rng = random.Random(seed); m = len(pairs); out = []
    for _ in range(n): s = [pairs[rng.randrange(m)] for _ in range(m)]; out.append(st.mean(s))
    out.sort(); return out[int(.1 * n)], out[int(.9 * n)]
res = {}; allpairs = defaultdict(list)
print(f"{'mode':<27}{'n0/n-7':>8}{'paired':>7} | {'dens 0':>7}{'dens -7':>8}{'Δ':>7}{'80%CI':>17}{'lower':>7} | {'free 0':>7}{'free -7':>8} | {'cont 0':>7}{'cont -7':>8}{'Δ':>8}{'higher':>7} | {'bin 0':>6}{'bin -7':>7}{'f→p':>4}{'p→f':>4} | {'acc 0':>6}{'acc -7':>7}")
for m in MODES:
    r0 = [r for r in rows if r["coef"] == 0 and r["mode"] == m]; r7 = [r for r in rows if r["coef"] == -7 and r["mode"] == m]
    ids = sorted({r["sample_id"] for r in r0} & {r["sample_id"] for r in r7})
    pd = [(dens(by[(-7, m, i)]) - dens(by[(0, m, i)])) for i in ids if dens(by[(0, m, i)]) is not None and dens(by[(-7, m, i)]) is not None]
    pc = [(by[(-7, m, i)]["continuous"] - by[(0, m, i)]["continuous"]) for i in ids if by[(0, m, i)]["continuous"] is not None and by[(-7, m, i)]["continuous"] is not None]
    fp = sum(1 for i in ids if by[(0, m, i)]["compliant"] is False and by[(-7, m, i)]["compliant"] is True); pf = sum(1 for i in ids if by[(0, m, i)]["compliant"] is True and by[(-7, m, i)]["compliant"] is False)
    mean = lambda xs: (st.mean([x for x in xs if x is not None]) if any(x is not None for x in xs) else None)
    d0, d7 = mean([dens(r) for r in r0]), mean([dens(r) for r in r7]); f0, f7 = mean([r.get("llm_n_sent") == 0 for r in r0 if r.get("llm_n_sent") is not None]), mean([r.get("llm_n_sent") == 0 for r in r7 if r.get("llm_n_sent") is not None])
    c0, c7 = mean([r["continuous"] for r in r0]), mean([r["continuous"] for r in r7]); b0, b7 = mean([r["compliant"] for r in r0]), mean([r["compliant"] for r in r7]); a0, a7 = mean([r["correct"] for r in r0]), mean([r["correct"] for r in r7])
    ci = boot(pd) if len(pd) >= 3 else (None, None)
    res[m] = {"n0": len(r0), "n7": len(r7), "paired": len(ids), "dens0": d0, "dens7": d7, "pd_mean": st.mean(pd) if pd else None, "pd_ci": ci, "pd_lower_share": (sum(x < 0 for x in pd) / len(pd)) if pd else None,
              "free0": f0, "free7": f7, "cont0": c0, "cont7": c7, "pc_mean": st.mean(pc) if pc else None, "pc_higher_share": (sum(x > 0 for x in pc) / len(pc)) if pc else None, "fp": fp, "pf": pf, "bin0": b0, "bin7": b7, "acc0": a0, "acc7": a7, "pd": pd, "pc": pc}
    for x in pd: allpairs["dens"].append(x)
    for x in pc: allpairs["cont"].append(x)
    f = lambda v, k="%.2f": ("    —" if v is None else (k % v))
    print(f"{m:<27}{len(r0):>4}/{len(r7):<3}{len(ids):>7} | {f(d0):>7}{f(d7):>8}{f(res[m]['pd_mean'],'%+.2f'):>7}{('[%+.1f,%+.1f]' % ci if ci[0] is not None else '—'):>17}{f(res[m]['pd_lower_share'],'%.2f'):>7} | {f(f0,'%.0f%%' if False else '%.2f'):>7}{f(f7):>8} | {f(c0,'%.3f'):>7}{f(c7,'%.3f'):>8}{f(res[m]['pc_mean'],'%+.3f'):>8}{f(res[m]['pc_higher_share']):>7} | {f(b0,'%.2f'):>6}{f(b7,'%.2f'):>7}{fp:>4}{pf:>4} | {f(a0):>6}{f(a7):>7}")
ad, ac = allpairs["dens"], allpairs["cont"]
print(f"\nALL MODES paired: narration density Δ {st.mean(ad):+.2f} per 1,000 words (80% CI [{boot(ad)[0]:+.2f}, {boot(ad)[1]:+.2f}], lower on {100*sum(x<0 for x in ad)/len(ad):.0f}% of {len(ad)} prompts); continuous compliance Δ {st.mean(ac):+.3f} (80% CI [{boot(ac)[0]:+.3f}, {boot(ac)[1]:+.3f}], higher on {100*sum(x>0 for x in ac)/len(ac):.0f}% of {len(ac)})")
json.dump({m: {k: v for k, v in d.items() if k not in ("pd", "pc")} for m, d in res.items()} | {"_all": {"dens_delta": st.mean(ad), "dens_ci": boot(ad), "cont_delta": st.mean(ac), "cont_ci": boot(ac), "n": len(ad)}}, open(REPO / "results/steer/s2_paired.json", "w"), indent=1)
# figure: two panels — paired density change per mode; paired continuous change per mode
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), dpi=150, sharey=True); ys = list(range(len(MODES)))[::-1]
for ax, key, lab, col in ((axes[0], "pd", "change in narration density (sentences / 1,000 words)", BLUE), (axes[1], "pc", "change in continuous compliance", ORANGE)):
    for y, m in zip(ys, MODES):
        v = res[m][key]
        if not v: continue
        ax.scatter([max(min(x, 12), -12) for x in v] if key == "pd" else v, [y] * len(v), s=22, color=BASE, zorder=3)
        ax.scatter(st.mean(v), y, s=90, color=col, edgecolor=SURF, linewidth=2, zorder=5); ax.text((12.4 if key == "pd" else 0.62), y, f"n={len(v)}", va="center", fontsize=8.5, color=MUTED)
    ax.axvline(0, color=INK2, lw=1); ax.xaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_color(BASE); ax.set_xlabel(lab, color=INK2)
    if key == "pd": ax.set_xlim(-13, 14)
    else: ax.set_xlim(-0.6, 0.7)
axes[0].set_yticks(ys); axes[0].set_yticklabels(MODES, color=INK2, fontsize=9)
axes[0].set_title("Narration: steered (−7) minus unsteered, same prompt", loc="left", fontsize=10.5, color=INK); axes[1].set_title("Compliance: steered minus unsteered, same prompt", loc="left", fontsize=10.5, color=INK)
fig.legend(handles=[Line2D([0],[0], marker="o", ls="", ms=6, color=BASE, label="one prompt"), Line2D([0],[0], marker="o", ls="", ms=9, color=BLUE, markeredgecolor=SURF, label="mode mean (narration)"), Line2D([0],[0], marker="o", ls="", ms=9, color=ORANGE, markeredgecolor=SURF, label="mode mean (compliance)")], frameon=False, loc="upper left", bbox_to_anchor=(0.01, 0.97), ncol=3, fontsize=9)
fig.suptitle("S2: steering against meta-discussion at layer 16, all nine modes (30 prompts each)", x=0.01, ha="left", fontsize=12, color=INK); fig.tight_layout(rect=(0, 0, 1, 0.9)); fig.savefig(REPO / "figures/steer_s2_paired.png", bbox_inches="tight"); plt.close(fig)
print("wrote results/steer/s2_paired.json, figures/steer_s2_paired.png")
