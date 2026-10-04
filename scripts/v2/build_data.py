#!/usr/bin/env python3
"""Build the v2 training sets for gpt-oss-20b (CONDITIONS_V2.md): arms A and B from the same base traces, then A1 = A's
exact traces with every prompt re-rendered in template T1.

    python scripts/v2/build_data.py --arms A,B --n-rows 920 [--limit 40]
Writes data/sft/v2_gptoss_{A,B,A1}.jsonl and results/v2_gptoss/build/{arm}_stats.json.
"""
from __future__ import annotations
import argparse, asyncio, json, os, random, sys, time
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
from cotctl.v2 import api as API; _API_MODEL = API.configure()
from cotctl.sft.editor import Editor
from cotctl.v2 import build as BD
from cotctl.v2.spec import C, role, TRAIN_TEMPLATES, LANG_NAME, K_PER_EXAMPLE


async def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", default="A,B"); ap.add_argument("--n-rows", type=int, default=920); ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--traces", default=str(REPO / "results/gptoss/sft/stage1_rollouts.jsonl")); ap.add_argument("--thresholds", default=str(REPO / "data/v2_thresholds_gpt-oss-20b.json"))
    ap.add_argument("--out-dir", default=str(REPO / "results/v2_gptoss/build")); ap.add_argument("--model", default=_API_MODEL); ap.add_argument("--attempts", type=int, default=5)
    ap.add_argument("--concurrency", type=int, default=16); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--suffix", default="")
    a = ap.parse_args(); out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True); th = json.load(open(a.thresholds))
    rs = [json.loads(l) for l in open(a.traces)]
    rs = [r for r in rs if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip() and (r.get("answer") or "").strip()]
    random.Random(a.seed).shuffle(rs); rs = rs[: a.n_rows]
    if a.limit: rs = rs[: a.limit]
    editor = Editor(model=a.model, cache_path=out_dir / "editor_cache.jsonl"); editor.temperature_override = 0.0
    judge = Editor(model=a.model, cache_path=out_dir / "judge_cache.jsonl"); judge.temperature_override = 0.0
    sem = asyncio.Semaphore(a.concurrency)
    for arm in a.arms.split(","):
        pool = [c[2] for c in C if role(c, arm) == "train"]; rng = random.Random(f"{a.seed}:{arm}"); usage = Counter()
        drawn, failed, kept = Counter(), Counter(), Counter(); rows_out, dropped = [], []; t0 = time.time()

        async def one(i, r):
            q = r["prompt"].split("Here is the question:\n\n", 1)[-1].strip()
            for attempt in range(a.attempts):
                conds = BD.sample_conds(pool, K_PER_EXAMPLE, usage, rng, lambda c: BD.eligible(c, q, r["reasoning"])); usage.update(conds)
                args = BD.make_args(conds, q, r["reasoning"], rng, th)
                if "ban_keyword" in conds and args["language"] != "en":  # ban the keyword in the trace language, not the English word
                    tr = await editor.call("Translate the given English word into the given language as it would appear in a sentence. Reply with the single translated word only.",
                                           f"Word: {args['keyword_en']}\nLanguage: {LANG_NAME[args['language']]}", temperature=0.0)
                    args["keyword"] = tr.strip().split()[0].strip(".,;:'\"").lower()
                row = BD.Row(i, q, conds, args, TRAIN_TEMPLATES[i % len(TRAIN_TEMPLATES)])
                async with sem:
                    try: text = await BD.compose(row, r["reasoning"], q, editor); v = await BD.verify(row, text, judge); v["_length"] = BD.length_ok(row, text, r["reasoning"])
                    except Exception as e: dropped.append({"i": i, "conds": conds, "error": f"{type(e).__name__}: {e}"}); continue
                drawn.update(conds); bad = [c for c, ok in v.items() if not ok]
                if not bad:
                    kept.update(conds)
                    rows_out.append({"messages": BD.training_messages(row, text, r["answer"]), "idx": i, "conds": conds, "args": args, "template": row.template,
                                     "question": q, "trace": text}); return
                from cotctl.third_party.redwood.instructions import word_count as _wc
                failed.update(bad); dropped.append({"i": i, "attempt": attempt, "conds": conds, "failed": bad, "args": args, "text": text[:700],
                                                    "words": _wc(text), "base_words": _wc(r["reasoning"])})
        await asyncio.gather(*(one(i, r) for i, r in enumerate(rs)))
        rows_out.sort(key=lambda x: x["idx"]); sfx = ("_dry" if a.limit else "") + a.suffix
        with open(REPO / f"data/sft/v2_gptoss_{arm}{sfx}.jsonl", "w") as f:
            for x in rows_out: f.write(json.dumps(x, ensure_ascii=False) + "\n")
        stats = {"arm": arm, "rows": len(rs), "kept": len(rows_out), "seconds": round(time.time() - t0), "pool": pool,
                 "per_condition": {c: {"drawn": drawn[c], "failed": failed[c], "kept": kept[c]} for c in pool},
                 "templates": dict(Counter(x["template"] for x in rows_out)), "languages": dict(Counter(x["args"]["language"] for x in rows_out)), "dropped": dropped[:400]}
        json.dump(stats, open(out_dir / f"{arm}_stats{sfx}.json", "w"), ensure_ascii=False, indent=1)
        print(f"arm {arm}: kept {len(rows_out)} / {len(rs)} in {time.time() - t0:.0f}s; templates {stats['templates']}; languages {stats['languages']}", flush=True)
        for c in pool: print(f"   {c:<26} drawn {drawn[c]:>4} failed {failed[c]:>3} kept {kept[c]:>4}", flush=True)
        if arm == "A":  # A1: the same traces, every prompt in T1
            with open(REPO / f"data/sft/v2_gptoss_A1{sfx}.jsonl", "w") as f:
                for x in rows_out:
                    row = BD.Row(x["idx"], x["question"], x["conds"], x["args"], "T1")
                    f.write(json.dumps({**x, "template": "T1", "messages": BD.training_messages(row, x["trace"], x["messages"][-1]["content"].split("</think>", 1)[1])}, ensure_ascii=False) + "\n")

if __name__ == "__main__": asyncio.run(main())
