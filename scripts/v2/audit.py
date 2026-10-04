#!/usr/bin/env python3
"""Leakage audit before training (CONDITIONS_V2.md, 'How leakage is avoided', check 4).

For every rule an arm holds out, its grader runs on the arm's finished training traces and on the base traces of the
same questions. A held-out rule that passes >= 10 points more often on training traces than on base traces is flagged:
training would teach it as a side effect. LLM-judged held-out rules are judged on a sample of 60 traces each.
Also checks that no held-out template's wording appears in any training prompt.

    python scripts/v2/audit.py --arms A,B,A1
Writes results/v2_gptoss/audit.json and prints a table.
"""
import argparse, asyncio, json, os, random, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
from cotctl.v2 import api as API; _API_MODEL = API.configure()
from cotctl.sft.editor import Editor
from cotctl.v2.runs import RUN
from cotctl.v2.spec import C, role, render, HELDOUT_TEMPLATES
from cotctl.v2.graders import grade, judge_many, JUDGED
from cotctl.v2.build import pick_keyword

HELD_PHRASES = ["private reasoning", "Quick one:", "while you're thinking it over", "Instructions for your thought process", "Then give your final answer as usual"]


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", default="A,B"); ap.add_argument("--suffix", default=""); ap.add_argument("--judge-n", type=int, default=60)
    a = ap.parse_args(); th = json.load(open(RUN["thresholds"]))
    base = {}
    for l in open(RUN["stage1"]):
        r = json.loads(l); base[r["prompt"].split("Here is the question:\n\n", 1)[-1].strip()] = r.get("reasoning") or ""
    judge = Editor(model=_API_MODEL, cache_path=RUN["root"] / "judge_cache.jsonl"); judge.temperature_override = 0.0
    report = {}
    for arm in a.arms.split(","):
        rows = [json.loads(l) for l in open(REPO / f"data/sft/{RUN['data_prefix']}_{arm}{a.suffix}.jsonl")]
        split = "A" if arm.startswith("A") else "B"
        held = [c[2] for c in C if role(c, split) == "test"]
        pairs = [(x["trace"], base.get(x["question"], ""), x["question"]) for x in rows if base.get(x["question"])]
        res = {}
        for cid in held:
            def args(q, t):
                d = {k: th[k] for k in "NMTW"}; d["language"] = "en"
                if cid == "ban_keyword": d["keyword"] = pick_keyword(q, t) or "zzzz"
                if cid == "foreign_summary": d["summary_language"] = "es"
                return d
            if cid in JUDGED:
                smp = random.Random(cid).sample(pairs, min(a.judge_n, len(pairs)))
                tr = await judge_many([(cid, t, args(q, t)) for t, _, q in smp], judge); bs = await judge_many([(cid, b, args(q, b)) for _, b, q in smp], judge)
                res[cid] = {"train": 100 * sum(tr) / len(tr), "base": 100 * sum(bs) / len(bs), "n": len(smp), "judged": True}
            else:
                tr = [bool(grade(cid, t, args(q, t))) for t, _, q in pairs]; bs = [bool(grade(cid, b, args(q, b))) for _, b, q in pairs]
                res[cid] = {"train": 100 * sum(tr) / len(tr), "base": 100 * sum(bs) / len(bs), "n": len(pairs), "judged": False}
            res[cid]["diff"] = res[cid]["train"] - res[cid]["base"]; res[cid]["flag"] = res[cid]["diff"] >= 10
        # length check: does a training rule change trace length relative to the base trace of the same question?
        import statistics as st
        from cotctl.third_party.redwood.instructions import word_count
        length = {}
        for cid in sorted({c for x in rows for c in x["conds"]}):
            ratios = [word_count(x["trace"]) / max(1, word_count(base[x["question"]])) for x in rows if cid in x["conds"] and base.get(x["question"])]
            if ratios: length[cid] = {"n": len(ratios), "median_ratio": round(st.median(ratios), 3), "flag": abs(st.median(ratios) - 1) > 0.15}
        allr = [word_count(x["trace"]) / max(1, word_count(base[x["question"]])) for x in rows if base.get(x["question"])]
        length["_all"] = {"n": len(allr), "median_ratio": round(st.median(allr), 3), "flag": abs(st.median(allr) - 1) > 0.15}
        prompts = [" ".join(m["content"] for m in x["messages"] if m["role"] != "assistant") for x in rows]
        tpl_leak = {p: sum(p.lower() in pr.lower() for pr in prompts) for p in HELD_PHRASES}
        report[arm] = {"held_out": res, "template_phrase_hits": tpl_leak, "n_rows": len(rows), "length": length}
        print(f"\n== arm {arm}: {len(rows)} rows; held-out rules (training traces vs base traces, % passing)")
        for cid, v in sorted(res.items(), key=lambda kv: -kv[1]["diff"]):
            print(f"  {'FLAG ' if v['flag'] else '     '}{cid:<26} train {v['train']:5.1f}  base {v['base']:5.1f}  diff {v['diff']:+5.1f}{'  (judged, n=' + str(v['n']) + ')' if v['judged'] else ''}")
        print("  held-out template phrases found in training prompts:", tpl_leak)
        print("  length check (median of training trace / base trace of the same question; flag if off by more than 15 %):")
        for cid, v in sorted(length.items(), key=lambda kv: kv[1]["median_ratio"]):
            print(f"    {'FLAG ' if v['flag'] else '     '}{cid:<26} x{v['median_ratio']:.2f}  (n={v['n']})")
    json.dump(report, open(RUN["root"] / f"audit{a.suffix}.json", "w"), indent=1)

if __name__ == "__main__": asyncio.run(main())
