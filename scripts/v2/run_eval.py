#!/usr/bin/env python3
"""Evaluate a gpt-oss checkpoint on the v2 grid (CONDITIONS_V2.md): 40 rules x 6 templates x 20 questions, one rule
per prompt, no answer tags. Questions come from Redwood's task pool (GSM8K, MATH, ARC, OpenBookQA, MMLU-Pro), never
from the training pool; number-notation rules use numeric questions only. The same questions are used for every
template and model.

    python scripts/v2/run_eval.py --label base --model openai/gpt-oss-20b
    python scripts/v2/run_eval.py --label A --model v2-A --grade-only
Writes results/v2_gptoss/eval/<label>/{rollouts,graded}.jsonl and summary.json.
"""
from __future__ import annotations
import argparse, asyncio, hashlib, json, os, random, re, sys
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
if not os.environ.get("EDITOR_API_KEY") and os.environ.get("JUDGE_API_KEY"):
    os.environ["EDITOR_API_KEY"] = os.environ["JUDGE_API_KEY"]; os.environ.setdefault("EDITOR_BASE_URL", os.environ.get("JUDGE_BASE_URL", "https://api.openai.com/v1"))
from cotctl.inference import Request, RolloutStore, SamplingParams, VLLMClient, run_sync, wait_for_server
from cotctl.third_party.redwood import scoring as RS
from cotctl.v2.spec import C, TEMPLATES, TRAIN_LANGS, rule_text, render, N_PROMPTS_PER_CELL
from cotctl.v2.graders import grade, judge_many, JUDGED
from cotctl.v2.build import pick_keyword
from cotctl.graders.reasonif import detect_language

NUMERIC = {"numbers_in_words", "roman_numerals"}
_norm = lambda q: re.sub(r"\W+", " ", q.lower()).strip()[:200]


def question_pool():
    train_q = {_norm(json.loads(l)["prompt"].split("Here is the question:\n\n", 1)[-1]) for l in open(REPO / "results/gptoss/sft/stage1_rollouts.jsonl")}
    tasks = [json.loads(l) for l in open(REPO / "data/redwood/tasks_all.jsonl")]
    pool = [t for t in tasks if t["source"] != "reasonif" and _norm(t["question"]) not in train_q and len(t["question"]) < 1500]
    return pool, len([t for t in tasks if _norm(t["question"]) in train_q])


def requests(th: dict):
    pool, overlap = question_pool(); out = []
    numeric = [t for t in pool if t["source"] in ("gsm8k", "math")]
    for c in C:
        cid = c[2]; src = numeric if cid in NUMERIC else pool
        rng = random.Random(f"v2eval:{cid}"); qs = []
        cand = sorted(src, key=lambda t: t["task_id"]); rng.shuffle(cand)
        for t in cand:
            if cid == "ban_keyword" and not pick_keyword(t["question"], t["question"]): continue
            qs.append(t)
            if len(qs) == N_PROMPTS_PER_CELL: break
        for j, t in enumerate(qs):
            a = {k: th[k] for k in "NMTW"}; a["language"] = "en"
            if cid == "given_language": a["language"] = TRAIN_LANGS[j % 4]
            if cid == "foreign_summary": a["summary_language"] = TRAIN_LANGS[j % 4]
            if cid == "ban_keyword": a["keyword"] = pick_keyword(t["question"], t["question"])
            q = t["question"].strip() + "\n\n" + RS.build_answer_instruction(t["answer_type"])
            for tid in TEMPLATES:
                dev, user = render(tid, [rule_text(cid, a)], q)
                out.append(Request(sample_id=t["task_id"], mode=f"{cid}|{tid}", prompt=user, developer=dev,
                                   meta={"cid": cid, "template": tid, "args": a, "answer": t["answer"], "answer_type": t["answer_type"],
                                         "n_options": t.get("n_options"), "source": t["source"], "rule": rule_text(cid, a)}))
    return out, overlap


_META = re.compile(r"\b(rule|requirement|instruction|constraint|formatting|format)s?\b", re.I)


def restates(reasoning: str, rule: str) -> bool:
    """Does the reasoning talk about the rule? A 4-word run from the rule text, or explicit talk of a rule/instruction."""
    rw = re.findall(r"\w+", rule.lower()); rs = " ".join(re.findall(r"\w+", reasoning.lower()))
    grams = {" ".join(rw[i:i + 4]) for i in range(len(rw) - 3)}
    return any(g in rs for g in grams) or bool(_META.search(reasoning))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--model", required=True)
    ap.add_argument("--base-url", default="http://localhost:8000/v1"); ap.add_argument("--grade-only", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=16384); ap.add_argument("--judge-model", default="gpt-4.1")
    ap.add_argument("--thresholds", default=str(REPO / "data/v2_thresholds_gpt-oss-20b.json")); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(); th = json.load(open(a.thresholds))
    out = REPO / "results/v2_gptoss/eval" / a.label; out.mkdir(parents=True, exist_ok=True); store = RolloutStore(out / "rollouts.jsonl")
    reqs, overlap = requests(th)
    if a.limit: reqs = reqs[: a.limit]
    print(f"{len(reqs)} requests; {overlap} task-pool questions also in training were excluded", flush=True)
    if not a.grade_only:
        wait_for_server(a.base_url)
        client = VLLMClient(a.model, a.base_url, concurrency=64)
        sp = SamplingParams(temperature=1.0, max_tokens=a.max_tokens, top_p=1.0, top_k=None, reasoning_effort="medium")
        with store: run_sync(client, reqs, sp, store, desc=f"v2/{a.label}")
    want = {r.key: r for r in reqs}
    rows = [r for r in store.read_all() if (r["sample_id"], r["mode"]) in want]
    graded, todo = [], []
    for r in rows:
        m = want[(r["sample_id"], r["mode"])].meta; t = r.get("reasoning") or ""; ok = r.get("think_status") == "ok" and t.strip() != ""
        g = grade(m["cid"], t, m["args"]) if ok else False
        acc = RS.score_accuracy(r.get("answer") or "", m["answer"], m["answer_type"], m.get("n_options"))
        rec = {"sample_id": r["sample_id"], "cid": m["cid"], "template": m["template"], "ok": ok, "truncated": bool(r.get("truncated")), "compliant": g,
               "correct": bool(acc), "restates": restates(t, m["rule"]) if ok else None, "words": len(t.split()), "lang": detect_language(t) if ok else None,
               "source": m["source"]}
        graded.append(rec)
        if g is None: todo.append((len(graded) - 1, m["cid"], t, m["args"]))
    if todo:
        from cotctl.sft.editor import Editor
        ed = Editor(model=a.judge_model, cache_path=REPO / "results/v2_gptoss/judge_cache.jsonl"); ed.temperature_override = 0.0
        res = asyncio.run(judge_many([(cid, t, ar) for _, cid, t, ar in todo], ed))
        for (i, *_), v in zip(todo, res): graded[i]["compliant"] = bool(v)
    with open(out / "graded.jsonl", "w") as f:
        for g in graded: f.write(json.dumps(g, ensure_ascii=False) + "\n")
    cell = defaultdict(list)
    for g in graded: cell[(g["cid"], g["template"])].append(g)
    summ = {f"{k[0]}|{k[1]}": {"n": len(v), "compliance": sum(bool(x["compliant"]) for x in v) / len(v), "accuracy": sum(x["correct"] for x in v) / len(v),
                                "restates": sum(bool(x["restates"]) for x in v) / len(v), "truncated": sum(x["truncated"] for x in v) / len(v)} for k, v in cell.items()}
    json.dump(summ, open(out / "summary.json", "w"), indent=1)
    print(a.label, "cells", len(summ), "mean compliance", round(sum(v["compliance"] for v in summ.values()) / max(1, len(summ)), 3), flush=True)


if __name__ == "__main__":
    main()
