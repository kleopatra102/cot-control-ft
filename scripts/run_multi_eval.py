#!/usr/bin/env python3
"""Run + grade the multi-constraint evaluation against a served model.

    scripts/serve_vllm.sh (with the merged checkpoint) &
    python scripts/run_multi_eval.py --label P2-step-final --model <served-name> [--limit N] [--grade-only]
Rollouts -> results/multi_eval/<label>/rollouts.jsonl (resumable); grades -> graded.jsonl; summary.json.
"""
from __future__ import annotations
import argparse, asyncio, json, os, statistics as st, sys
from collections import defaultdict
from pathlib import Path
import yaml
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
from cotctl.inference import RolloutStore, SamplingParams, VLLMClient, run_sync, wait_for_server
from cotctl.eval import score_answer, cotcontrol_answer_key
from cotctl.graders.continuous import count_keyword_uses
from cotctl.multi_eval import reasonif_multi_requests, cotcontrol_multi_requests, grade_reasonif_multi, grade_cotcontrol_multi

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--model", default=None); ap.add_argument("--config", default=str(REPO / "configs/base.yaml"))
    ap.add_argument("--word-limits", default=str(REPO / "data/word_limits_Qwen3.5-9B.json")); ap.add_argument("--limit", type=int, default=None, help="debug: cap requests per suite")
    ap.add_argument("--grade-only", action="store_true"); ap.add_argument("--no-judge", action="store_true"); ap.add_argument("--suites", default="reasonif,cotcontrol")
    ap.add_argument("--n-single-cc", type=int, default=100); ap.add_argument("--n-pair-cc", type=int, default=60); ap.add_argument("--n-triple-cc", type=int, default=60)
    a = ap.parse_args(); cfg = yaml.safe_load(open(a.config)); out = REPO / "results/multi_eval" / a.label; out.mkdir(parents=True, exist_ok=True)
    wl = json.load(open(a.word_limits)); wl = wl.get("Qwen3.5-9B", wl)
    reqs = []
    if "reasonif" in a.suites: reqs += reasonif_multi_requests(wl)
    if "cotcontrol" in a.suites: reqs += cotcontrol_multi_requests(a.n_single_cc, a.n_pair_cc, a.n_triple_cc)
    if a.limit:
        by = defaultdict(list)
        for r in reqs: by[r.meta["suite"]].append(r)
        reqs = [r for rs in by.values() for r in rs[: a.limit]]
    store = RolloutStore(out / "rollouts.jsonl")
    if not a.grade_only:
        model = a.model or cfg["model"]["served_name"]; wait_for_server(cfg["server"]["base_url"])
        client = VLLMClient(model, cfg["server"]["base_url"], concurrency=cfg["server"]["concurrency"]); sampling = SamplingParams(**dict(cfg["sampling"]))
        print(f"{len(reqs)} requests ({len(store)} already stored) -> {out}", flush=True)
        with store: run_sync(client, reqs, sampling, store, desc=f"multi-eval/{a.label}")
    rollouts = store.read_all(); print(f"grading {len(rollouts)} rollouts", flush=True)
    judged = {}
    if not a.no_judge:
        from cotctl.judge import LLMJudge
        pend = [r for r in rollouts if "ignore_question" in r["meta"].get("modes", []) and r.get("think_status") == "ok" and (r.get("reasoning") or "").strip()]
        if pend:
            judge = LLMJudge(model=os.environ.get("JUDGE_MODEL", "gpt-5-mini"), cache_path=out / "judge_cache.jsonl", concurrency=int(cfg["judge"].get("concurrency", 16)))  # OpenAI direct via JUDGE_API_KEY/JUDGE_BASE_URL
            vs = asyncio.run(judge.judge_many("ignore_question", [(r["prompt"], r["reasoning"]) for r in pend], desc="ignore_question judge"))
            judged = {(r["sample_id"], r["mode"]): v.compliant for r, v in zip(pend, vs)}
    unc = {r["sample_id"]: count_keyword_uses(r["reasoning"] or "", r["meta"].get("keywords") or []) for r in rollouts if r["mode"] == "unconstrained" and r.get("think_status") == "ok"}
    key = cotcontrol_answer_key(); graded = []
    for r in rollouts:
        if r["mode"] == "unconstrained": continue
        suite = r["meta"]["suite"]
        g = grade_reasonif_multi(r) if suite == "reasonif_multi" else grade_cotcontrol_multi(r, judged, unc)
        correct = score_answer("reasonif" if suite == "reasonif_multi" else "cotcontrol", r.get("answer") or "", r["meta"].get("correct_answer", ""), key.get(r["sample_id"]) or r["meta"].get("correct_letter"))
        graded.append({"sample_id": r["sample_id"], "mode": r["mode"], "suite": suite, "level": r["meta"]["level"], "held_out": r["meta"].get("held_out", False), "constraints": r["meta"].get("constraints") or r["meta"].get("modes"),
                       "think_status": r.get("think_status"), "truncated": bool(r.get("truncated")), "completion_tokens": r.get("completion_tokens", 0), "correct": correct, **g})
    with open(out / "graded.jsonl", "w") as f:
        for g in graded: f.write(json.dumps(g, ensure_ascii=False) + "\n")
    def mean(xs): xs = [x for x in xs if x is not None]; return (st.mean(xs) if xs else None)
    summ = {"label": a.label, "n_rollouts": len(rollouts), "conditions": {}}
    for mode in sorted({g["mode"] for g in graded}):
        gs = [g for g in graded if g["mode"] == mode]; ok = [g for g in gs if g["think_status"] == "ok"]
        cons = gs[0]["constraints"]
        summ["conditions"][mode] = {"suite": gs[0]["suite"], "level": gs[0]["level"], "held_out": gs[0]["held_out"], "n": len(gs), "gradeable": len(ok), "truncated": mean([g["truncated"] for g in gs]),
            "joint_binary": mean([g["joint"] for g in ok]), "per_binary": {c: mean([g["per_binary"].get(c) for g in ok]) for c in cons}, "per_continuous": {c: mean([g["per_continuous"].get(c) for g in ok]) for c in cons},
            "accuracy": mean([g["correct"] for g in gs])}
    for suite in ("reasonif_multi", "cotcontrol_multi"):
        for lvl in (1, 2, 3):
            for held in (False, True):
                cs = [c for c in summ["conditions"].values() if c["suite"] == suite and c["level"] == lvl and c["held_out"] == held]
                if cs: summ[f"{suite}/k{lvl}{'/heldout' if held else ''}/joint_macro"] = mean([c["joint_binary"] for c in cs])
    json.dump(summ, open(out / "summary.json", "w"), indent=1)
    print(f"\n{'condition':<58}{'n':>4}{'ok':>4}{'joint%':>7}{'acc%':>6}  per-constraint binary")
    for m, c in summ["conditions"].items():
        pb = " ".join(f"{k.split('_')[0][:5]}={(100*v):.0f}" if v is not None else f"{k[:5]}=—" for k, v in c["per_binary"].items())
        print(f"{m:<58}{c['n']:>4}{c['gradeable']:>4}{(100*c['joint_binary'] if c['joint_binary'] is not None else float('nan')):>7.1f}{(100*c['accuracy'] if c['accuracy'] is not None else float('nan')):>6.0f}  {pb}")
    print({k: round(v, 3) for k, v in summ.items() if k.endswith("joint_macro") and v is not None})
    return 0

if __name__ == "__main__": raise SystemExit(main())
