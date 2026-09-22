#!/usr/bin/env python3
"""Evaluate steered rollouts: binary + continuous compliance, accuracy, truncation, regex meta rate and the
full-trace LLM narration rate (gpt-5-mini lister, cached), per (layer, coef, mode). Writes
results/steer/steered_eval.json and figures/steer_dose_response.png; prints the table.

    python scripts/steer/eval_steered.py --label base [--no-llm]
"""
from __future__ import annotations
import argparse, asyncio, glob, json, re, statistics as st, sys
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env", override=True)
from cotctl.eval import grade_rollout, cotcontrol_answer_key
from cotctl.graders.continuous import count_keyword_uses
from cotctl.graders.continuous_v2 import score_v2

def load(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]

async def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--label", default="base"); ap.add_argument("--no-llm", action="store_true"); ap.add_argument("--concurrency", type=int, default=16); a = ap.parse_args()
    files = sorted(glob.glob(str(REPO / f"results/steer/rollouts_{a.label}_cotcontrol_*_L*_mean_c*.jsonl")))
    key = cotcontrol_answer_key()
    kw = {r["sample_id"]: r["meta"].get("keywords") or [] for r in load(REPO / f"results/{a.label}/cotcontrol_rollouts.jsonl") if r["mode"] in ("word_suppression", "multiple_word_suppression")}
    unc = {r["sample_id"]: count_keyword_uses(r.get("reasoning") or "", kw[r["sample_id"]]) for r in load(REPO / f"results/{a.label}/unconstrained_rollouts.jsonl") if r["sample_id"] in kw and r.get("think_status") == "ok"}
    rows = []
    for f in files:
        m = re.search(r"_L(\d+)_mean_c([+-][\d.]+)\.jsonl$", f); L, c = int(m.group(1)), float(m.group(2))
        for r in load(f):
            g = grade_rollout(r, None, key)
            cont = score_v2(r["mode"], r["reasoning"] or "", keywords=r["meta"].get("keywords") or [], unconstrained_uses=unc.get(r["sample_id"])) if g.think_status == "ok" else None
            rows.append({"layer": L, "coef": c, "mode": r["mode"], "sample_id": r["sample_id"], "prompt": r["prompt"], "reasoning": r["reasoning"] or "", "ok": g.think_status == "ok", "truncated": g.truncated,
                         "compliant": g.compliant, "continuous": cont, "correct": g.correct, "regex_meta": g.meta_discussion, "tokens": g.completion_tokens, "reasoning_words": g.reasoning_words})
    # LLM narration lister on usable traces
    if not a.no_llm:
        from cotctl.judge import LLMJudge
        judge = LLMJudge(model="gpt-5-mini", cache_path=REPO / "results/strip_llm/judge_cache.jsonl", concurrency=a.concurrency)
        items = [r for r in rows if r["ok"] and r["reasoning"].strip()]
        verd = await judge.judge_many("narration_full", [(r["prompt"], r["reasoning"]) for r in items], desc="narration lister")
        for r, v in zip(items, verd):
            r["llm_meta"] = (bool(v.compliant) if v.error is None else None); r["llm_n_sent"] = (len(json.loads(v.detail)) if v.error is None and v.detail else None); r["llm_error"] = v.error
    for r in rows: r.pop("prompt"); r.pop("reasoning")
    # aggregate
    def mean(xs): xs = [x for x in xs if x is not None]; return st.mean(xs) if xs else None
    agg = []
    for (L, c, m), rs in sorted(defaultdict(list, {k: [r for r in rows if (r["layer"], r["coef"], r["mode"]) == k] for k in {(r["layer"], r["coef"], r["mode"]) for r in rows}}).items()):
        ok = [r for r in rs if r["ok"]]
        agg.append({"layer": L, "coef": c, "mode": m, "n": len(rs), "gradeable": len(ok), "truncated": mean([r["truncated"] for r in rs]), "binary": mean([r["compliant"] for r in ok]), "continuous": mean([r["continuous"] for r in ok]),
                    "accuracy": mean([r["correct"] for r in rs]), "regex_meta": mean([r["regex_meta"] for r in ok]), "llm_meta": mean([r.get("llm_meta") for r in ok]), "llm_n_sent": mean([r.get("llm_n_sent") for r in ok]), "llm_judged": sum(r.get("llm_meta") is not None for r in ok),
                    "tokens": mean([r["tokens"] for r in rs]), "words": mean([r["reasoning_words"] for r in ok]),
                    "llm_density": mean([1000 * r["llm_n_sent"] / r["reasoning_words"] for r in ok if r.get("llm_n_sent") is not None and r["reasoning_words"] > 0])})
    json.dump({"rows": rows, "agg": agg}, open(REPO / "results/steer/steered_eval.json", "w"), indent=1)
    f = lambda x, p=False: "    —" if x is None else (f"{100*x:5.1f}" if p else f"{x:5.3f}")
    print(f"{'layer':>5} {'coef':>6} {'mode':<20} {'n':>3} {'ok':>3} {'trunc%':>6} | {'bin%':>6} {'cont':>6} {'acc%':>6} | {'regex%':>7} {'LLM%':>6} {'sent':>5} | {'tokens':>7}")
    for g in agg:
        print(f"{g['layer']:>5} {g['coef']:>+6.0f} {g['mode']:<20} {g['n']:>3} {g['gradeable']:>3} {f(g['truncated'],1):>6} | {f(g['binary'],1):>6} {f(g['continuous']):>6} {f(g['accuracy'],1):>6} | {f(g['regex_meta'],1):>7} {f(g['llm_meta'],1):>6} {(f'{g['llm_n_sent']:5.1f}' if g['llm_n_sent'] is not None else '    —'):>5} | {g['tokens']:>7.0f}")
    # figure: dose-response at each layer, narration (LLM) and continuous compliance vs coef, per mode
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        SURF, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"; RAMP = {12: "#86b6ef", 16: "#2a78d6", 20: "#104281"}
        plt.rcParams.update({"font.family": "sans-serif", "font.size": 10, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": BASE, "axes.facecolor": SURF, "figure.facecolor": SURF, "savefig.facecolor": SURF, "axes.spines.top": False, "axes.spines.right": False})
        modes = sorted({g["mode"] for g in agg}); metrics = [("llm_density", "narration sentences per 1,000 words (LLM lister)", False), ("continuous", "continuous compliance", False), ("accuracy", "accuracy, %", True)]
        fig, axes = plt.subplots(len(modes), len(metrics), figsize=(4.2 * len(metrics), 3.2 * len(modes)), dpi=150, squeeze=False)
        for i, m in enumerate(modes):
            for j, (k, lab, pct) in enumerate(metrics):
                ax = axes[i][j]
                base = [g for g in agg if g["mode"] == m and g["coef"] == 0]
                for L in sorted({g["layer"] for g in agg if g["coef"] != 0}):
                    pts = sorted([(g["coef"], g[k]) for g in agg if g["mode"] == m and (g["layer"] == L or g["coef"] == 0) and g[k] is not None])
                    ax.plot([p[0] for p in pts], [(100 * p[1] if pct else p[1]) for p in pts], marker="o", ms=6, lw=2, color=RAMP.get(L, INK2), markeredgecolor=SURF, label=f"layer {L}")
                ax.axvline(0, color=GRID, lw=1); ax.yaxis.grid(True, color=GRID, lw=1); ax.set_axisbelow(True); ax.tick_params(length=0); ax.spines["left"].set_visible(False)
                if i == len(modes) - 1: ax.set_xlabel("steering coefficient (× unit direction)", color=INK2)
                ax.set_title(f"{m} — {lab}", loc="left", fontsize=10, color=INK)
                if pct: ax.set_ylim(0, 100)
        axes[0][0].legend(frameon=False, fontsize=9)
        fig.suptitle("Steering against the meta-discussion direction: dose-response", x=0.01, ha="left", fontsize=12, color=INK); fig.tight_layout(rect=(0, 0, 1, 0.96)); fig.savefig(REPO / "figures/steer_dose_response.png"); plt.close(fig)
        print("wrote figures/steer_dose_response.png")
    except Exception as e: print("figure skipped:", e)
    return 0

if __name__ == "__main__": raise SystemExit(asyncio.run(main()))
