#!/usr/bin/env python3
"""Figures for STEERING_RESULTS.md from results/steer/*. Palette/rules: dataviz reference instance."""
from __future__ import annotations
import json, random, sys, statistics as st
from pathlib import Path
import torch
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
REPO = Path(__file__).resolve().parents[2]; OUT = REPO / "figures"; sys.path.insert(0, str(REPO / "src"))
from cotctl.steer.directions import auroc, project, mean_diff
SURF, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, AQUA, LIGHT, DARK = "#2a78d6", "#eb6834", "#1baf7a", "#86b6ef", "#104281"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": BASE,
    "axes.facecolor": SURF, "figure.facecolor": SURF, "savefig.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})
def style(ax): ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.spines["left"].set_visible(False); ax.tick_params(length=0)

# ---- Fig 1: probe AUROC by layer (E1b)
T = json.load(open(REPO / "results/steer/directions_base_cotcontrol_base_s.json"))
fig, ax = plt.subplots(figsize=(8, 3.8), dpi=150)
for pooling, col, lab in (("mean", BLUE, "mean-pooled"), ("last", LIGHT, "last-token")):
    rows = [r for r in T if r["pooling"] == pooling]; L = [r["layer"] for r in rows]
    ax.plot(L, [r["heldout_q_auroc"] for r in rows], marker="o", ms=7, lw=2, color=col, markeredgecolor=SURF, label=f"{lab}: held-out questions")
    if pooling == "mean":
        ax.plot(L, [r["heldout_mode_auroc"] for r in rows], marker="s", ms=6, lw=2, color=DARK, markeredgecolor=SURF, label="mean-pooled: leave-one-mode-out")
        ax.plot(L, [r["transfer_auroc"] for r in rows], marker="D", ms=6, lw=2, color=AQUA, markeredgecolor=SURF, label="mean-pooled: transfer to ReasonIF")
        ax.plot(L, [r["probe"] for r in rows], lw=1.5, ls=":", color=INK2, label="logistic-probe ceiling")
        ax.plot(L, [r["random"] for r in rows], lw=1.5, ls=":", color=BASE, label="random direction")
ax.set_ylim(0.2, 1.0); ax.set_xticks([8, 12, 16, 20, 24]); ax.set_xlabel("layer", color=INK2); ax.set_ylabel("AUROC", color=INK2); style(ax)
ax.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=2); ax.set_title("The meta-discussion direction: separation is flat across depth and at the probe ceiling", loc="left", fontsize=11, color=INK)
fig.tight_layout(); fig.savefig(OUT / "steer_probe_by_layer.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig 2 + 3: per-mode AUROC at L16 and projection distributions
D = torch.load(REPO / "results/steer/acts_base_cotcontrol_base_s.pt"); R = torch.load(REPO / "results/steer/acts_base_reasonif_base.pt"); DIR = torch.load(REPO / "results/steer/directions_base_cotcontrol_base_s.pt")
li = D["layers"].index(16); u = DIR["directions"][16]["mean"]
X = D["mean"][:, li]; y = torch.tensor([m["is_narration"] for m in D["meta"]]); modes = [m["mode"] for m in D["meta"]]; s = project(X, u)
Xr = R["mean"][:, li]; yr = torch.tensor([m["is_narration"] for m in R["meta"]]); mr = [m["mode"] for m in R["meta"]]; sr = project(Xr, u)
items = [(m, auroc(s[torch.tensor([x == m for x in modes])], y[torch.tensor([x == m for x in modes])]), BLUE) for m in sorted(set(modes))] + \
        [(m, auroc(sr[torch.tensor([x == m for x in mr])], yr[torch.tensor([x == m for x in mr])]), AQUA) for m in sorted(set(mr))]
items.sort(key=lambda t: -t[1]); fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150); ys = list(range(len(items)))[::-1]
for yy, (m, a, col) in zip(ys, items):
    ax.plot([0.5, a], [yy, yy], color=GRID, lw=2, zorder=2); ax.scatter(a, yy, s=64, color=col, edgecolor=SURF, linewidth=2, zorder=4); ax.text(a + 0.012, yy, f"{a:.2f}", va="center", fontsize=8.5, color=INK2)
ax.axvline(0.5, color=BASE, lw=1); ax.set_xlim(0.45, 1.0); ax.set_yticks(ys); ax.set_yticklabels([m for m, _, _ in items], color=INK2, fontsize=9); ax.xaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_color(BASE)
ax.set_xlabel("AUROC of projection onto the layer-16 direction (fitted on CoTControl)", color=INK2)
ax.legend(handles=[Line2D([0], [0], marker="o", ls="", ms=8, color=BLUE, markeredgecolor=SURF, label="CoTControl mode"), Line2D([0], [0], marker="o", ls="", ms=8, color=AQUA, markeredgecolor=SURF, label="ReasonIF type (transfer)")], frameon=False, loc="lower right", fontsize=9)
ax.set_title("One direction separates narration in every condition, including the benchmark it was not fitted on", loc="left", fontsize=10.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / "steer_auroc_per_mode.png", bbox_inches="tight"); plt.close(fig)
fig, ax = plt.subplots(figsize=(8, 3.6), dpi=150)
bins = torch.linspace(-10, 12, 45)
for mask, col, lab in ((~y, BASE, "non-narration sentences (matched)"), (y, BLUE, "narration sentences (LLM-labelled)")):
    h = torch.histc(s[mask], bins=44, min=-10, max=12) / int(mask.sum()); ax.bar(bins[:-1], h, width=0.5, color=col, alpha=0.85 if col == BLUE else 1, label=lab, zorder=3)
ax.axvline(0, color=GRID, lw=1); style(ax); ax.set_xlabel("projection onto the unit direction (activation units; mean ‖activation‖ ≈ 31)", color=INK2); ax.set_ylabel("share of sentences", color=INK2)
ax.legend(frameon=False, fontsize=9); ax.set_title(f"Layer 16: narration sits at +{s[y].mean():.1f} ± {s[y].std():.1f}, non-narration at {s[~y].mean():.1f} ± {s[~y].std():.1f}", loc="left", fontsize=11, color=INK)
fig.tight_layout(); fig.savefig(OUT / "steer_projection_hist.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig 4: E2 structure — per-condition style cosines (heatmap) + paired consistency by layer
P = torch.load(REPO / "results/steer/pairacts_base_base.pt"); meta = P["meta"]; layers = P["layers"]; n = len(meta)
rng = random.Random(0); idx = list(range(n)); rng.shuffle(idx); trs = set(idx[: int(.7 * n)]); tr = torch.tensor([i in trs for i in range(n)]); te = ~tr
un = lambda v: v / (v.norm() + 1e-8)
fig, axes = plt.subplots(1, 2, figsize=(10, 3.9), dpi=150, gridspec_kw={"width_ratios": [1, 1.3]})
ax = axes[0]; li16 = layers.index(16); A, B, C, Dq = (P[k][:, li16] for k in "ABCD"); conds = sorted(set((m["suite"], m["mode"]) for m in meta))
us = {c: mean_diff(Dq[torch.tensor([(x["suite"], x["mode"]) == c for x in meta])], C[torch.tensor([(x["suite"], x["mode"]) == c for x in meta])])[1] for c in conds}
M = torch.tensor([[float(us[a] @ us[b]) for b in conds] for a in conds]); im = ax.imshow(M, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("b", ["#cde2fb", "#2a78d6", "#0d366b"]), vmin=0, vmax=1)
for i in range(len(conds)):
    for j in range(len(conds)): ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=9, color=SURF if M[i, j] > 0.55 else INK)
ax.set_xticks(range(len(conds))); ax.set_yticks(range(len(conds))); ax.set_xticklabels([c[1] for c in conds], rotation=30, ha="right", fontsize=8.5, color=INK2); ax.set_yticklabels([c[1] for c in conds], fontsize=8.5, color=INK2); ax.tick_params(length=0)
ax.set_title("Style directions\ncosine between conditions, layer 16", loc="left", fontsize=10, color=INK)
ax = axes[1]
series = {"style (D−C)": [], "instruction (A−C)": [], "controllability residual": [], "residual orthogonal to style & instruction": []}
for lj, L in enumerate(layers):
    A, B, C, Dq = (P[k][:, lj] for k in "ABCD"); usd = un((Dq[tr] - C[tr]).mean(0)); ui = un((A[tr] - C[tr]).mean(0)); res = (B - A) - (Dq - C); uc = un(res[tr].mean(0))
    def orth(v): v = v - (v @ usd)[:, None] * usd; return v - (v @ ui)[:, None] * ui
    ro = orth(res); uo = un(ro[tr].mean(0))
    series["style (D−C)"].append(float((((Dq[te] - C[te]) @ usd) > 0).float().mean())); series["instruction (A−C)"].append(float((((A[te] - C[te]) @ ui) > 0).float().mean()))
    series["controllability residual"].append(float(((res[te] @ uc) > 0).float().mean())); series["residual orthogonal to style & instruction"].append(float(((ro[te] @ uo) > 0).float().mean()))
for (lab, v), col, mk in zip(series.items(), (LIGHT, AQUA, BLUE, DARK), ("o", "s", "D", "^")): ax.plot(layers, [100 * x for x in v], marker=mk, ms=6, lw=2, color=col, markeredgecolor=SURF, label=lab)
ax.axhline(50, color=BASE, lw=1); ax.set_ylim(40, 102); ax.set_xticks(layers); style(ax); ax.set_xlabel("layer", color=INK2); ax.set_ylabel("held-out quartets with positive projection, %", color=INK2)
ax.legend(frameon=False, fontsize=8.5, loc="lower left"); ax.set_title("Paired consistency of the four directions\n47 held-out quartets", loc="left", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(OUT / "steer_e2_structure.png", bbox_inches="tight"); plt.close(fig)

# ---- Fig 5: S1 usable band (closed think blocks) + paired narration-density deltas
E = json.load(open(REPO / "results/steer/steered_eval_base.json")); agg = E["agg"]; rows = E["rows"]
fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.9), dpi=150)
ax = axes[0]; coefs = [-14, -7, 0, 7]; Ls = [12, 16, 20]; ramp = {12: LIGHT, 16: BLUE, 20: DARK}
for L in Ls:
    pts = []
    for c in coefs:
        cells = [g for g in agg if g["coef"] == c and (g["layer"] == L or c == 0)]
        if cells: pts.append((c, 100 * sum(g["gradeable"] for g in cells) / sum(g["n"] for g in cells)))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=7, lw=2, color=ramp[L], markeredgecolor=SURF, label=f"layer {L}")
ax.set_ylim(0, 100); ax.set_xticks(coefs); style(ax); ax.set_xlabel("steering coefficient", color=INK2); ax.set_ylabel("rollouts with a closed think block, %", color=INK2); ax.legend(frameon=False, fontsize=9)
ax.set_title("Usable band\nrollouts that still terminate, by layer and coefficient", loc="left", fontsize=9.5, color=INK)
ax = axes[1]
dens = {(r["layer"], r["coef"], r["mode"], r["sample_id"]): 1000 * r["llm_n_sent"] / r["reasoning_words"] for r in rows if r["ok"] and r.get("llm_n_sent") is not None and r["reasoning_words"] > 0}
base = {(m, s_): v for (L, c, m, s_), v in dens.items() if c == 0}
cells = [(L, c, m) for L in (16, 20) for c in (-7, 7) for m in ("uppercase_thinking", "word_suppression")]
ys = list(range(len(cells)))[::-1]
for yy, (L, c, m) in zip(ys, cells):
    d = [dens[(L, c, m, s_)] - base[(m, s_)] for (LL, cc, mm, s_) in dens if (LL, cc, mm) == (L, c, m) and (m, s_) in base]
    if not d: continue
    dc = [min(x, 19.5) for x in d]
    ax.scatter(dc, [yy] * len(d), s=28, color=BASE, zorder=3); ax.scatter(st.mean(d), yy, s=90, color=ramp[L], edgecolor=SURF, linewidth=2, zorder=5, clip_on=True); ax.text(min(max(dc) + 0.6, 17.5), yy, f"n={len(d)}" + (" (mean off-scale)" if st.mean(d) > 20 else ""), va="center", fontsize=8.5, color=MUTED)
ax.axvline(0, color=INK2, lw=1); ax.set_xlim(-12, 20); ax.set_yticks(ys); ax.set_yticklabels([f"L{L} {c:+d}  {m.split('_')[0]}" for L, c, m in cells], fontsize=8.5, color=INK2); ax.xaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_color(BASE)
ax.set_xlabel("change in narration density vs unsteered, same prompt (sentences per 1,000 words)", color=INK2, fontsize=9)
ax.set_title("Paired narration change per prompt (grey) and cell mean (coloured)\none outlier at +50 clipped", loc="left", fontsize=9.5, color=INK)
fig.tight_layout(); fig.savefig(OUT / "steer_s1_band_and_paired.png", bbox_inches="tight"); plt.close(fig)
print("wrote", sorted(p.name for p in OUT.glob("steer_*.png")))
