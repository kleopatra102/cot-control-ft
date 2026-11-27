"""Figures for results/rl_local/PROG_EVAL_G_RESULTS.md. Run from the repo root with the project venv."""
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
R = Path("results"); OUT = R / "rl_local/prog_eval_g_figs"
M = {"r1qwen7": "R1-Distill-Qwen-7B", "r1llama": "R1-Distill-Llama-8B"}
C_CTRL, C_TREAT, C_BASE, INK, INK2, GRID = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
cmp = {m: json.load(open(R / m / "prog_eval_g/compare.json")) for m in M}
def L(p): return [json.loads(l) for l in open(p)]
def per_rule(m, arm, kind):
    d = {}
    for g in L(R / m / f"prog_eval_g/{arm}/graded.jsonl"):
        if g["kind"] == kind: d.setdefault(g["rules"][0], []).append(bool(g["usable"] and g["compliant"]))
    return {k: 100 * sum(v) / len(v) for k, v in d.items()}

# Fig 1: mean compliance, control vs treated, trained and held-out, per model
fig, axs = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
for ax, m in zip(axs, M):
    for i, kind in enumerate(["trained", "held_out"]):
        t = cmp[m][kind]["treated_vs_control"]
        for j, (v, c, lab) in enumerate([(t["reference"], C_CTRL, "control"), (t["arm"], C_TREAT, "treated")]):
            ax.bar(i + (j - .5) * .36, 100 * v, .34, color=c, label=lab if i == 0 else None, edgecolor="#fcfcfb", linewidth=2)
            ax.text(i + (j - .5) * .36, 100 * v + 1, f"{100*v:.1f}", ha="center", va="bottom", fontsize=9, color=INK)
        lo, hi = t["gain_95"]
        ax.text(i, 44, f"gain {t['gain']:.2f}\n[{lo:.2f}, {hi:.2f}]", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks([0, 1], ["trained rules (39)", "held-out rules (27)"]); ax.set_title(M[m], fontsize=10.5, color=INK)
    ax.set_ylim(0, 52); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
axs[0].set_ylabel("rule compliance, % of rollouts"); axs[0].legend(frameon=False, loc="upper right", bbox_to_anchor=(1, .82))
fig.tight_layout(); fig.savefig(OUT / "fig1_compliance.png", dpi=160); plt.close(fig)

# Fig 2/3: per-rule compliance, control vs treated (dumbbell), per model
for n, kind in [(2, "trained"), (3, "held_out")]:
    fig, axs = plt.subplots(1, 2, figsize=(10, 0.24 * (39 if kind == "trained" else 27) + 1.4), sharey=False)
    for ax, m in zip(axs, M):
        c, t = per_rule(m, "Bpctrlg", kind), per_rule(m, "Bpg", kind)
        ks = sorted(c, key=lambda k: t[k] - c[k])
        for y, k in enumerate(ks):
            ax.plot([c[k], t[k]], [y, y], color=GRID, lw=2, zorder=1)
        ax.scatter([c[k] for k in ks], range(len(ks)), s=26, color=C_CTRL, label="control", zorder=2, edgecolor="#fcfcfb", linewidth=1)
        ax.scatter([t[k] for k in ks], range(len(ks)), s=26, color=C_TREAT, label="treated", zorder=3, edgecolor="#fcfcfb", linewidth=1)
        ax.set_yticks(range(len(ks)), ks, fontsize=7.5); ax.set_xlim(-3, 103); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
        ax.set_title(M[m], fontsize=10.5, color=INK); ax.set_xlabel("compliance, % of 50 prompts")
    axs[0].legend(frameon=False, loc="lower right")
    fig.suptitle(f"{'Trained' if kind == 'trained' else 'Held-out'} rules, sorted by treated minus control", fontsize=11, color=INK)
    fig.tight_layout(); fig.savefig(OUT / f"fig{n}_{kind}_per_rule.png", dpi=160); plt.close(fig)

# Fig 4: answer accuracy, old grader vs fixed grader
sets = [("P0", "no rules"), ("trained", "trained rules"), ("held_out", "held-out rules"), ("P2", "bundles")]
fig, axs = plt.subplots(2, 2, figsize=(9, 5.6), sharey=True)
for r, m in enumerate(M):
    for col, (f, ttl) in enumerate([("graded_v1.jsonl", "old grader (ignored <answer> tags)"), ("graded.jsonl", "fixed grader")]):
        ax = axs[r, col]
        for j, (arm, cl, lab) in enumerate([("base", C_BASE, "base"), ("Bpctrlg", C_CTRL, "control"), ("Bpg", C_TREAT, "treated")]):
            g = L(R / m / f"prog_eval_g/{arm}/{f}")
            for i, (s, _) in enumerate(sets):
                x = [v for v in g if (v["set"] == s if s in ("P0", "P2") else v["kind"] == s)]
                if not x: continue
                acc = 100 * sum(bool(v["correct"]) for v in x) / len(x)
                ax.bar(i + (j - 1) * .27, acc, .25, color=cl, label=lab if i == 1 or (arm == "base" and i == 0) else None, edgecolor="#fcfcfb", linewidth=1.5)
        ax.set_xticks(range(4), [s[1] for s in sets], fontsize=8.5); ax.set_ylim(0, 100); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
        ax.set_title(f"{M[m]}: {ttl}", fontsize=9.5, color=INK)
    axs[r, 0].set_ylabel("answer accuracy, %")
h, l = axs[0, 0].get_legend_handles_labels(); seen = dict(zip(l, h)); axs[0, 1].legend(seen.values(), seen.keys(), frameon=False, ncol=3, loc="upper right", fontsize=8.5)
fig.tight_layout(); fig.savefig(OUT / "fig4_accuracy.png", dpi=160); plt.close(fig)
print("ok")
