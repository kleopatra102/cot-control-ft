#!/usr/bin/env python3
"""Unlearning data (UNLEARNING_V2_PLAN.md, step 2) for one model, sampled through Tinker.

  traces  the model's own unconstrained reasoning on the v2 stage-1 training questions (prompt "Think step-by-step.
          Here is the question: ..."), plus the screening's 200 unconstrained traces (evaluation-pool questions that are in
          no evaluation grid). No rule in the prompt.
  pairs   U: each trace paired with ONE rule from the model's trained operations (headroom operations of its unlearned
          half, data/unlearn_v2_splits.json), drawn uniformly, in template T1, T2 or T3; kept only if the grader confirms
          the trace breaks the rule (up to 3 draws per trace). The answer is the model's own; nothing is rewritten.
          C: the same traces under their original prompt (no rule).
  audit   selection check: held-out rules' graders on the kept traces against all traces (the filter could shift, say,
          length). Flags a held-out rule whose pass rate moves by 10 points or more.

  .venv-tinker/bin/python scripts/v2/unlearn_build.py --model qwen38_tinker traces --n 700
  .venv-tinker/bin/python scripts/v2/unlearn_build.py --model qwen38_tinker pairs
  .venv-tinker/bin/python scripts/v2/unlearn_build.py --model qwen38_tinker audit
Writes results/unlearn_v2/<model>/{traces.jsonl, audit.json} and data/sft/unlearn_v2_<model>_{U,C}.jsonl.
"""
from __future__ import annotations
import argparse, asyncio, json, random, statistics as st, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
from cotctl.v2 import api as API; _API_MODEL = API.configure()
from cotctl.inference import Request, RolloutStore, SamplingParams, run_sync
from cotctl.v2.spec import C, TRAIN_LANGS, TRAIN_TEMPLATES, render
from cotctl.v2.graders import grade, judge_many, JUDGED
from cotctl.v2.build import pick_keyword, eligible, localized_rule

MODELS = {"qwen38_tinker": dict(tinker="Qwen/Qwen3.8-27B", renderer="qwen3_8_medium_reasoning",
                                sampling=dict(temperature=1.0, top_p=0.95, top_k=20), max_tokens=12288)}
STAGE1_Q = REPO / "results/gptoss/sft/stage1_rollouts.jsonl"  # the v2 stage-1 question pool (937 questions)
STAGE1_PROMPT = "Think step-by-step.\n\nHere is the question:\n\n{q}"


def load_split(model):
    s = json.load(open(REPO / "data/unlearn_v2_splits.json"))[model]
    trained = [r for o in s["unlearn"] if o["headroom"] for r in o["rules"]]
    held = [r for o in s["held_out"] for r in o["rules"]]
    return trained, held


def cmd_traces(a, cfg, out):
    qs = []
    for l in open(STAGE1_Q):
        r = json.loads(l); q = r["prompt"].split("Here is the question:\n\n", 1)[-1].strip()
        if q not in {x[1] for x in qs}: qs.append((r["sample_id"], q))
    rng = random.Random(f"unlearn-traces:{a.model}"); rng.shuffle(qs); qs = qs[: a.n]
    reqs = [Request(sample_id=f"s1:{sid}", mode="plain", prompt=STAGE1_PROMPT.format(q=q), meta={"question": q, "source": "stage1"}) for sid, q in qs]
    from cotctl.tinker_client import TinkerClient
    client = TinkerClient(cfg["tinker"], cfg["renderer"], concurrency=64)
    store = RolloutStore(out / "traces.jsonl")
    with store: run_sync(client, reqs, SamplingParams(max_tokens=cfg["max_tokens"], **cfg["sampling"]), store, desc=f"{a.model}/traces")
    # append the screening's unconstrained traces (same model and settings), once
    have = {r["sample_id"] for r in store.read_all()}
    with open(out / "traces.jsonl", "a") as f:
        for l in open(REPO / f"results/screen_v2/{a.model}/calib.jsonl"):
            r = json.loads(l); r["sample_id"] = "calib:" + r["sample_id"]
            if r["sample_id"] in have: continue
            r["meta"] = {**r.get("meta", {}), "source": "screen_calib"}; f.write(json.dumps(r) + "\n")
    rows = [r for r in store.read_all()]
    print(f"{len(rows)} traces; ok {sum(r['think_status'] == 'ok' for r in rows)}; truncated {sum(bool(r.get('truncated')) for r in rows)}")


def args_for(cid, q, t, th, rng):
    d = {k: th[k] for k in "NMTW"}; d["language"] = "en"
    if cid == "given_language": d["language"] = rng.choice(TRAIN_LANGS)
    if cid == "foreign_summary": d["summary_language"] = rng.choice(TRAIN_LANGS)
    if cid == "ban_keyword": d["keyword"] = d["keyword_en"] = pick_keyword(q, t) or "zzzz"
    return d


async def cmd_pairs(a, cfg, out):
    trained, _ = load_split(a.model); th = json.load(open(REPO / f"results/screen_v2/{a.model}/thresholds.json"))
    rows = [json.loads(l) for l in open(out / "traces.jsonl")]
    rows = [r for r in rows if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip() and (r.get("answer") or "").strip()]
    rng = random.Random(f"unlearn-pairs:{a.model}")
    cands = []  # (row, [(cid, args, template), ...] up to 3 draws)
    for r in rows:
        q = r["meta"]["question"]; t = r["reasoning"]; draws = []
        for _ in range(3):
            cid = rng.choice([c for c in trained if eligible(c, q, t)])
            draws.append((cid, args_for(cid, q, t, th, rng), rng.choice(TRAIN_TEMPLATES)))
        cands.append((r, draws))
    # grade every draw (judge for the LLM-graded rules), keep the first draw the trace breaks
    jobs = [(i, k, cid, ar) for i, (r, ds) in enumerate(cands) for k, (cid, ar, _) in enumerate(ds) if cid in JUDGED]
    res = {}
    if jobs:
        from cotctl.sft.editor import Editor
        ed = Editor(model=_API_MODEL, cache_path=out / "judge_cache.jsonl"); ed.temperature_override = 0.0
        vs = await judge_many([(cid, cands[i][0]["reasoning"], ar) for i, k, cid, ar in jobs], ed)
        res = {(i, k): bool(v) for (i, k, *_), v in zip(jobs, vs)}
    U, Cc, kept_by = [], [], {}
    for i, (r, ds) in enumerate(cands):
        for k, (cid, ar, tid) in enumerate(ds):
            passes = res[(i, k)] if cid in JUDGED else bool(grade(cid, r["reasoning"], ar))
            if passes: continue
            q = r["meta"]["question"]
            qtext = r["prompt"] if r["meta"]["source"] == "screen_calib" else q  # calib prompts already carry the answer line
            dev, user = render(tid, [localized_rule(cid, ar)], qtext)
            asst = {"role": "assistant", "content": f"<think>\n{r['reasoning'].strip()}\n</think>\n\n{r['answer'].strip()}"}
            U.append({"messages": ([{"role": "developer", "content": dev}] if dev else []) + [{"role": "user", "content": user}, asst],
                      "id": r["sample_id"], "cid": cid, "template": tid, "args": ar, "question": q, "trace": r["reasoning"]})
            Cc.append({"messages": [{"role": "user", "content": r["prompt"]}, asst], "id": r["sample_id"], "question": q, "trace": r["reasoning"]})
            kept_by[cid] = kept_by.get(cid, 0) + 1
            break
    for name, data in (("U", U), ("C", Cc)):
        p = REPO / f"data/sft/unlearn_v2_{a.model}_{name}.jsonl"
        with open(p, "w") as f:
            for x in data: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(f"{len(rows)} usable traces -> {len(U)} pairs (U) and {len(Cc)} (C); rules: {dict(sorted(kept_by.items()))}; "
          f"templates: { {t: sum(x['template'] == t for x in U) for t in TRAIN_TEMPLATES} }")


async def cmd_audit(a, cfg, out):
    _, held = load_split(a.model); th = json.load(open(REPO / f"results/screen_v2/{a.model}/thresholds.json"))
    allr = [json.loads(l) for l in open(out / "traces.jsonl")]
    allr = [r for r in allr if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip()]
    kept_ids = {json.loads(l)["id"] for l in open(REPO / f"data/sft/unlearn_v2_{a.model}_U.jsonl")}
    kept = [r for r in allr if r["sample_id"] in kept_ids]
    rng = random.Random("audit")
    rep = {}
    for cid in held:
        if cid in JUDGED: continue  # judged held-out rules: not audited here (their pass rates on base traces are near 0)
        f = lambda rs: 100 * st.mean(bool(grade(cid, r["reasoning"], args_for(cid, r["meta"]["question"], r["reasoning"], th, rng))) for r in rs)
        k, b = f(kept), f(allr); rep[cid] = {"kept": round(k, 1), "all": round(b, 1), "diff": round(k - b, 1), "flag": abs(k - b) >= 10}
    wc = lambda rs: st.median(len(r["reasoning"].split()) for r in rs)
    rep["_length"] = {"kept_median_words": wc(kept), "all_median_words": wc(allr)}
    json.dump(rep, open(out / "audit.json", "w"), indent=1)
    for cid, v in rep.items(): print(cid, v)


def cmd_relearn(a, cfg, out):
    """Relearning data: base model, prompts asking for one HELD-OUT headroom rule (T1-T3) on stage-1 questions not used for
    the unlearning traces; keep the samples the grader says comply. Writes data/sft/unlearn_v2_<model>_relearn<n>.jsonl."""
    s = json.load(open(REPO / "data/unlearn_v2_splits.json"))[a.model]
    held = [r for o in s["held_out"] if o["headroom"] for r in o["rules"]]
    th = json.load(open(REPO / f"results/screen_v2/{a.model}/thresholds.json"))
    used = {json.loads(l)["meta"]["question"] for l in open(out / "traces.jsonl")}
    qs = []
    for l in open(STAGE1_Q):
        q = json.loads(l)["prompt"].split("Here is the question:\n\n", 1)[-1].strip()
        if q not in used and q not in qs: qs.append(q)
    rng = random.Random(f"relearn:{a.model}"); reqs = []
    for i in range(a.n_prompts):
        q = qs[i % len(qs)]; cid = rng.choice([c for c in held if eligible(c, q, q)]); ar = args_for(cid, q, q, th, rng); tid = rng.choice(TRAIN_TEMPLATES)
        dev, user = render(tid, [localized_rule(cid, ar)], q)
        reqs.append(Request(sample_id=f"rl{i}", mode=cid, prompt=user, developer=dev, meta={"question": q, "cid": cid, "args": ar, "template": tid}))
    from cotctl.tinker_client import TinkerClient
    client = TinkerClient(cfg["tinker"], cfg["renderer"], concurrency=64)
    store = RolloutStore(out / "relearn_samples.jsonl")
    with store: run_sync(client, reqs, SamplingParams(max_tokens=cfg["max_tokens"], **cfg["sampling"]), store, desc=f"{a.model}/relearn")
    rows = [r for r in store.read_all() if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip() and (r.get("answer") or "").strip()]
    keep = []
    jobs = [r for r in rows if r["meta"]["cid"] in JUDGED]
    jv = {}
    if jobs:
        from cotctl.sft.editor import Editor
        ed = Editor(model=_API_MODEL, cache_path=out / "judge_cache.jsonl"); ed.temperature_override = 0.0
        vs = asyncio.run(judge_many([(r["meta"]["cid"], r["reasoning"], r["meta"]["args"]) for r in jobs], ed)); jv = {r["sample_id"]: bool(v) for r, v in zip(jobs, vs)}
    for r in rows:
        m = r["meta"]; ok = jv[r["sample_id"]] if m["cid"] in JUDGED else bool(grade(m["cid"], r["reasoning"], m["args"]))
        if ok: keep.append(r)
    rng.shuffle(keep)
    for n in a.sizes:
        with open(REPO / f"data/sft/unlearn_v2_{a.model}_relearn{n}.jsonl", "w") as f:
            for r in keep[:n]:
                asst = {"role": "assistant", "content": f"<think>\n{r['reasoning'].strip()}\n</think>\n\n{r['answer'].strip()}"}
                msgs = ([{"role": "developer", "content": r["meta"].get("dev")}] if False else []) + [{"role": "user", "content": r["prompt"]}, asst]
                f.write(json.dumps({"messages": msgs, "cid": r["meta"]["cid"]}, ensure_ascii=False) + "\n")
    by = {}
    for r in keep: by[r["meta"]["cid"]] = by.get(r["meta"]["cid"], 0) + 1
    print(f"{len(rows)} samples, {len(keep)} compliant ({100 * len(keep) / max(1, len(rows)):.0f} %); by rule {dict(sorted(by.items()))}")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True)
    sp = ap.add_subparsers(dest="cmd", required=True)
    t = sp.add_parser("traces"); t.add_argument("--n", type=int, default=700)
    sp.add_parser("pairs"); sp.add_parser("audit")
    rl = sp.add_parser("relearn"); rl.add_argument("--n-prompts", type=int, default=300); rl.add_argument("--sizes", type=int, nargs="+", default=[64])
    a = ap.parse_args(); cfg = MODELS[a.model]; out = REPO / "results/unlearn_v2" / a.model; out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "traces": cmd_traces(a, cfg, out)
    elif a.cmd == "pairs": asyncio.run(cmd_pairs(a, cfg, out))
    elif a.cmd == "relearn": cmd_relearn(a, cfg, out)
    else: asyncio.run(cmd_audit(a, cfg, out))


if __name__ == "__main__":
    main()
