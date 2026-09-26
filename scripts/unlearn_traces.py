#!/usr/bin/env python3
"""Phase-2 (unlearning) source traces: the starting model answers CoTControl questions that are NOT in the
300-question evaluation draw, with the plain question prompt (no Requirement line). See UNLEARNING_PLAN.md.

    scripts/serve_vllm.sh Q5-final=results/qwen3_8b/ckpts/Q5/step-final &
    python scripts/unlearn_traces.py --model Q5-final

Resumable: rollouts are keyed by (sample_id, "unconstrained") in results/unlearn/traces.jsonl.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import yaml
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
from cotctl.inference import Request, RolloutStore, SamplingParams, VLLMClient, run_sync, wait_for_server
from cotctl.datasets import load_cotcontrol
from cotctl.eval import cotcontrol_samples
from cotctl.multi_eval import cotcontrol_multi_prompt


def unlearn_questions(n_eval: int = 300, seed: int = 42):
    """Every CoTControl question with valid keywords that is not in the evaluation draw."""
    held = {s.id for s in cotcontrol_samples(n_eval, seed)}
    return [s for s in load_cotcontrol() if s.metadata.get("valid_keywords") and s.id not in held]


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--model", required=True, help="served model or adapter name"); ap.add_argument("--config", default=str(REPO / "configs/base.yaml"))
    ap.add_argument("--out", default=str(REPO / "results/unlearn/traces.jsonl")); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(); cfg = yaml.safe_load(open(a.config)); out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    qs = unlearn_questions()
    if a.limit: qs = qs[: a.limit]
    reqs = []
    for s in qs:
        kws = s.metadata.get("valid_keywords") or s.metadata.get("keywords") or []
        reqs.append(Request(sample_id=s.id, mode="unconstrained", prompt=cotcontrol_multi_prompt(s.question, s.options, [], kws),
                            meta={"dataset": s.dataset, "keywords": kws, "correct_answer": s.correct_answer, "correct_letter": s.metadata.get("answer_letter"), "n_options": len(s.options or [])}))
    store = RolloutStore(out); wait_for_server(cfg["server"]["base_url"])
    client = VLLMClient(a.model, cfg["server"]["base_url"], concurrency=cfg["server"]["concurrency"]); sampling = SamplingParams(**dict(cfg["sampling"]))
    print(f"{len(reqs)} questions outside the evaluation draw ({len(store)} already stored) -> {out}", flush=True)
    with store: run_sync(client, reqs, sampling, store, desc="unlearn/traces")
    rs = store.read_all(); ok = sum(1 for r in rs if r.get("think_status") == "ok")
    print(f"done: {len(rs)} rollouts, {ok} with a closed think block", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
