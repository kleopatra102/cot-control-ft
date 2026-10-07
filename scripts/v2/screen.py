#!/usr/bin/env python3
"""Screen a base model's own CoT controllability on the v2 rules (UNLEARNING_V2_PLAN.md, step 1).

1. Unconstrained traces on --n-calib pool questions (no rule) -> thresholds N, M, T, W for this model, and each rule's
   pass rate when nobody asked for it (the chance rate).
2. Reduced v2 grid: 40 rules x templates T1-T3 x --n-q questions x --samples samples, one rule per prompt. The questions
   are the first --n-q of the v2 evaluation questions for each rule (run_eval.py), so the screen is a subset of the
   grid gpt-oss and Gemma were evaluated on.
3. Scores per rule: plain (sample 0), best of k (any sample satisfies), chance rate; macro over operations.

    python scripts/v2/screen.py --name qwen36 --model nvidia/Qwen3.6-35B-A3B-NVFP4 --sampling '{"temperature":1.0,"top_p":0.95,"top_k":20}'
Writes results/screen_v2/<name>/{calib,grid}.jsonl, thresholds.json, graded.jsonl, summary.json.
"""
from __future__ import annotations
import argparse, asyncio, json, random, statistics as st, subprocess, sys
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(Path(__file__).parent))
import run_eval as RE  # noqa: E402  (v2 question pool, request grid, restates; configures the judge API)
from cotctl.inference import Request, RolloutStore, SamplingParams, VLLMClient, run_sync, wait_for_server
from cotctl.third_party.redwood import scoring as RS
from cotctl.v2.spec import C, TRAIN_TEMPLATES
from cotctl.v2.graders import grade, judge_many, JUDGED
from cotctl.v2.build import pick_keyword

OP = {c[2]: (c[0], c[1]) for c in C}


def macro(per_rule: dict) -> float:
    ops = defaultdict(list)
    for cid, v in per_rule.items(): ops[OP[cid]].append(v)
    return st.mean(st.mean(v) for v in ops.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--model", required=True); ap.add_argument("--sampling", default="{}")
    ap.add_argument("--system-file", default=None, help="system prompt some models need to think (Magistral)")
    ap.add_argument("--n-q", type=int, default=10); ap.add_argument("--samples", type=int, default=3); ap.add_argument("--n-calib", type=int, default=200)
    ap.add_argument("--templates", default=",".join(TRAIN_TEMPLATES)); ap.add_argument("--max-tokens", type=int, default=12288)
    ap.add_argument("--base-url", default="http://localhost:8000/v1"); ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--grade-only", action="store_true", help="re-grade the stored rollouts without a server")
    ap.add_argument("--backend", choices=("vllm", "tinker"), default="vllm", help="tinker: sample through Tinker (run with .venv-tinker)")
    ap.add_argument("--renderer", default=None, help="tinker-cookbook renderer for --backend tinker, e.g. deepseekv3_thinking")
    a = ap.parse_args()
    out = REPO / "results/screen_v2" / a.name; out.mkdir(parents=True, exist_ok=True)
    system = open(a.system_file).read().strip() if a.system_file else None
    sp = SamplingParams(max_tokens=a.max_tokens, **json.loads(a.sampling))
    if not a.grade_only and a.backend == "tinker":
        from cotctl.tinker_client import TinkerClient
        client = TinkerClient(a.model, a.renderer, concurrency=a.concurrency)
    elif not a.grade_only: wait_for_server(a.base_url); client = VLLMClient(a.model, a.base_url, concurrency=a.concurrency)

    # 1. unconstrained traces -> thresholds and chance rates
    grid0, _ = RE.requests({"N": 100, "M": 300, "T": 0.2, "W": 5.0})  # thresholds only change rule wording; questions do not depend on them
    used = {r.sample_id for r in grid0}
    pool, _ = RE.question_pool(); rng = random.Random("screen-calib")
    calib_q = [t for t in sorted(pool, key=lambda t: t["task_id"]) if t["task_id"] not in used]; rng.shuffle(calib_q); calib_q = calib_q[: a.n_calib]
    calib = [Request(sample_id=t["task_id"], mode="plain", system=system, prompt=t["question"].strip() + "\n\n" + RS.build_answer_instruction(t["answer_type"]),
                     meta={"question": t["question"], "answer": t["answer"], "answer_type": t["answer_type"], "n_options": t.get("n_options")}) for t in calib_q]
    cstore = RolloutStore(out / "calib.jsonl")
    if not a.grade_only:
        with cstore: run_sync(client, calib, sp, cstore, desc=f"{a.name}/calib")
    th_path = out / "thresholds.json"
    subprocess.run([sys.executable, str(REPO / "scripts/v2/calibrate.py"), "--traces", str(out / "calib.jsonl"), "--out", str(th_path)], check=True)
    th = json.load(open(th_path))
    crow = [r for r in cstore.read_all() if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip()]
    calib_acc = st.mean(bool(RS.score_accuracy(r.get("answer") or "", r["meta"]["answer"], r["meta"]["answer_type"], r["meta"].get("n_options"))) for r in crow) if crow else None

    # 2. reduced grid with k samples
    grid, _ = RE.requests(th)
    tids = a.templates.split(","); first = defaultdict(list)
    for r in grid:
        if r.meta["cid"] not in first or (r.sample_id not in first[r.meta["cid"]] and len(first[r.meta["cid"]]) < a.n_q): first[r.meta["cid"]].append(r.sample_id)
    reqs = [Request(sample_id=r.sample_id, mode=f"{r.mode}|s{k}", prompt=r.prompt, developer=r.developer, system=system, meta={**r.meta, "k": k})
            for r in grid if r.meta["template"] in tids and r.sample_id in first[r.meta["cid"]] for k in range(a.samples)]
    print(f"{a.name}: {len(reqs)} grid requests", flush=True)
    gstore = RolloutStore(out / "grid.jsonl")
    if not a.grade_only:
        with gstore: run_sync(client, reqs, sp, gstore, desc=f"{a.name}/grid")

    # 3. grade grid (programmatic + judge) and chance rates on the unconstrained traces
    want = {r.key: r for r in reqs}; graded, todo = [], []
    for r in gstore.read_all():
        if (r["sample_id"], r["mode"]) not in want: continue
        m = want[(r["sample_id"], r["mode"])].meta; t = r.get("reasoning") or ""; ok = r.get("think_status") == "ok" and t.strip() != ""
        g = grade(m["cid"], t, m["args"]) if ok else False
        graded.append({"sample_id": r["sample_id"], "cid": m["cid"], "template": m["template"], "k": m["k"], "ok": ok, "truncated": bool(r.get("truncated")),
                       "compliant": g, "correct": bool(RS.score_accuracy(r.get("answer") or "", m["answer"], m["answer_type"], m.get("n_options"))),
                       "restates": RE.restates(t, m["rule"]) if ok else None, "words": len(t.split())})
        if g is None: todo.append((len(graded) - 1, m["cid"], t, m["args"]))
    chance_todo, chance = [], defaultdict(list)
    for r in crow:
        q = r["meta"]["question"]
        for c in C:
            cid = c[2]; ar = {**{k: th[k] for k in "NMTW"}, "language": "es", "summary_language": "es", "keyword": pick_keyword(q, q) or "zzzz"}
            if cid not in JUDGED: chance[cid].append(bool(grade(cid, r["reasoning"], ar)))
            elif sum(x[0] == cid for x in chance_todo) < 40: chance_todo.append((cid, r["reasoning"], ar))  # judge 40 traces per judged rule
    if todo or chance_todo:
        from cotctl.sft.editor import Editor
        ed = Editor(model=RE._API_MODEL, cache_path=REPO / "results/screen_v2/judge_cache.jsonl"); ed.temperature_override = 0.0
        res = asyncio.run(judge_many([(cid, t, ar) for _, cid, t, ar in todo] + chance_todo, ed))
        for (i, *_), v in zip(todo, res[: len(todo)]): graded[i]["compliant"] = bool(v)
        for (cid, *_), v in zip(chance_todo, res[len(todo):]): chance[cid].append(bool(v))
    with open(out / "graded.jsonl", "w") as f:
        for g in graded: f.write(json.dumps(g) + "\n")

    cell = defaultdict(dict)  # (cid, template, question) -> {k: compliant}
    for g in graded: cell[(g["cid"], g["template"], g["sample_id"])][g["k"]] = bool(g["compliant"])
    plain, bestk = defaultdict(list), defaultdict(list)
    for (cid, _, _), ks in cell.items():
        plain[cid].append(ks.get(0, False)); bestk[cid].append(any(ks.values()))
    rule = {cid: {"plain": 100 * st.mean(plain[cid]), "best_of_k": 100 * st.mean(bestk[cid]), "chance": 100 * st.mean(chance[cid]) if chance[cid] else 0.0}
            for cid in plain}
    above = lambda key: macro({c: max(0.0, v[key] - v["chance"]) for c, v in rule.items()})
    s0 = [g for g in graded if g["k"] == 0]
    summ = {"name": a.name, "model": a.model, "thresholds": th, "n_grid": len(graded), "samples": a.samples, "templates": tids,
            "macro_plain": macro({c: v["plain"] for c, v in rule.items()}), "macro_best_of_k": macro({c: v["best_of_k"] for c, v in rule.items()}),
            "macro_chance": macro({c: v["chance"] for c, v in rule.items()}), "macro_plain_above_chance": above("plain"), "macro_best_above_chance": above("best_of_k"),
            "accuracy": 100 * st.mean(g["correct"] for g in s0), "accuracy_unconstrained": None if calib_acc is None else 100 * calib_acc,
            "truncated": 100 * st.mean(g["truncated"] for g in s0), "restates": 100 * st.mean(bool(g["restates"]) for g in s0),
            "median_words": st.median(g["words"] for g in s0), "rules": rule}
    json.dump(summ, open(out / "summary.json", "w"), indent=1)
    print(json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in summ.items() if k not in ("rules", "thresholds")}), flush=True)


if __name__ == "__main__":
    main()
