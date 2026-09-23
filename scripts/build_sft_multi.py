#!/usr/bin/env python3
"""Stage 2 for the multi-constraint arms. Reuses results/sft/stage1_rollouts.jsonl (937 questions).

    python scripts/build_sft_multi.py --arm P2 --n-rows 920 [--limit 24] [--editor-model gpt-4.1-mini]
Writes data/sft/multi_<ARM>.jsonl, results/multi/<ARM>_plan.json, results/multi/<ARM>_stats.json.
Editor: EDITOR_API_KEY / EDITOR_BASE_URL (falls back to JUDGE_* then OPENROUTER); temperature pinned to 0.
"""
from __future__ import annotations
import argparse, asyncio, json, logging, os, sys, time
from collections import Counter, defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
if not os.environ.get("EDITOR_API_KEY") and os.environ.get("JUDGE_API_KEY"):
    os.environ["EDITOR_API_KEY"] = os.environ["JUDGE_API_KEY"]; os.environ.setdefault("EDITOR_BASE_URL", os.environ.get("JUDGE_BASE_URL", "https://api.openai.com/v1"))
from cotctl.inference import RolloutStore
from cotctl.sft.build import TrainingRow, write_training_jsonl
from cotctl.sft.editor import Editor
from cotctl.sft.transforms import TransformContext
from cotctl.sft.multi import plan_multi, compose, verify, holdouts
from cotctl.prompts import reasonif_baseline_prompt
log = logging.getLogger("build_sft_multi")

async def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--arm", required=True, choices=["S1", "P2", "T3", "M"]); ap.add_argument("--n-rows", type=int, default=920)
    ap.add_argument("--limit", type=int, default=None); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--editor-model", default="gpt-4.1-mini"); ap.add_argument("--concurrency", type=int, default=12)
    a = ap.parse_args(); out_dir = REPO / "results/multi"; out_dir.mkdir(parents=True, exist_ok=True)
    rollouts = {r["sample_id"]: r for r in RolloutStore(REPO / "results/sft/stage1_rollouts.jsonl").read_all()}
    questions = [r["prompt"].split("Here is the question:\n\n", 1)[-1] for r in rollouts.values() if r.get("think_status") == "ok" and (r.get("answer") or "").strip()]
    ho = holdouts(); plan = plan_multi(questions, a.arm, min(a.n_rows, len(questions)), a.seed, ho)
    if a.limit: plan = plan[: a.limit]
    editor = Editor(model=a.editor_model, cache_path=out_dir / "editor_cache.jsonl"); editor.temperature_override = 0.0
    print(f"arm {a.arm}: {len(plan)} rows; editor {a.editor_model} @ T=0; held-out pairs {[sorted(c) for c in ho[2]]}; triples {[sorted(c) for c in ho[3]]}", flush=True)
    rows, dropped, per_combo = [], [], defaultdict(lambda: Counter()); sem = asyncio.Semaphore(a.concurrency); t0 = time.time()
    async def one(m):
        async with sem:
            r = rollouts.get(m.question_id)
            if r is None: dropped.append({"row_idx": m.row_idx, "constraints": m.constraints, "reason": "no stage-1"}); return
            ctx = TransformContext(question=m.question, full_prompt=reasonif_baseline_prompt(m.question), editor=editor)
            try: edited = await compose(m, r["reasoning"], ctx)
            except Exception as e: dropped.append({"row_idx": m.row_idx, "constraints": m.constraints, "reason": f"transform: {e}"}); per_combo["+".join(m.constraints)]["error"] += 1; return
            v = verify(m, edited); key = "+".join(m.constraints); per_combo[key]["n"] += 1
            if all(v.values()):
                per_combo[key]["pass"] += 1
                rows.append(TrainingRow(row_idx=m.row_idx, question_id=m.question_id, mode="+".join(m.constraints), prompt=m.training_prompt(), reasoning=edited, answer=(r.get("answer") or "").strip(), constraint_args={**m.args, "constraints": m.constraints}))
            else:
                bad = [k for k, ok in v.items() if not ok]; dropped.append({"row_idx": m.row_idx, "constraints": m.constraints, "args": m.args, "failed": bad})
                for k in bad: per_combo[key][f"fail:{k}"] += 1
    await asyncio.gather(*(one(m) for m in plan))
    rows.sort(key=lambda x: x.row_idx); out = REPO / f"data/sft/multi_{a.arm}{'_dry' if a.limit else ''}.jsonl"; write_training_jsonl(rows, out)
    json.dump([{"row_idx": m.row_idx, "question_id": m.question_id, "constraints": m.constraints, "args": m.args} for m in plan], open(out_dir / f"{a.arm}_plan.json", "w"), ensure_ascii=False, indent=1)
    stats = {"arm": a.arm, "planned": len(plan), "kept": len(rows), "dropped": len(dropped), "seconds": round(time.time() - t0), "per_combo": {k: dict(v) for k, v in per_combo.items()}, "dropped_rows": dropped[:200], "holdouts": {str(k): [sorted(c) for c in v] for k, v in ho.items()}}
    json.dump(stats, open(out_dir / f"{a.arm}_stats{'_dry' if a.limit else ''}.json", "w"), ensure_ascii=False, indent=1)
    print(f"kept {len(rows)} / {len(plan)} in {time.time()-t0:.0f}s -> {out.name}"); fails = Counter(k for d in dropped for k in d.get("failed", [])); print("failures by constraint:", dict(fails))
    for k, v in sorted(per_combo.items(), key=lambda kv: -kv[1]["n"])[:12]: print(f"  {k:<60} n={v['n']:>3} pass={v.get('pass',0):>3}")
    return 0

if __name__ == "__main__": raise SystemExit(asyncio.run(main()))
