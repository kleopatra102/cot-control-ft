#!/usr/bin/env python3
"""Matched-reasoning control arm R: the model's own unconstrained stage-1 traces under the plain ReasonIF prompt,
no constraint, no editing. Same questions and row count as the constraint arms. Writes data/sft/<prefix>_R.jsonl."""
import argparse, random, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.inference import RolloutStore
from cotctl.prompts import reasonif_baseline_prompt
from cotctl.sft.build import TrainingRow, write_training_jsonl
ap = argparse.ArgumentParser(); ap.add_argument("--rollouts", required=True); ap.add_argument("--data-prefix", required=True)
ap.add_argument("--n-rows", type=int, default=920); ap.add_argument("--seed", type=int, default=42); a = ap.parse_args()
rs = [r for r in RolloutStore(a.rollouts).read_all() if r.get("think_status") == "ok" and (r.get("answer") or "").strip()]
random.Random(a.seed).shuffle(rs); rs = rs[: a.n_rows]
rows = []
for i, r in enumerate(rs):
    q = r["prompt"].split("Here is the question:\n\n", 1)[-1]
    rows.append(TrainingRow(row_idx=i, question_id=r["sample_id"], mode="none", prompt=reasonif_baseline_prompt(q), reasoning=r["reasoning"], answer=r["answer"].strip(), constraint_args={"constraints": []}))
out = REPO / f"data/sft/{a.data_prefix}_R.jsonl"; write_training_jsonl(rows, out); print(f"wrote {len(rows)} rows -> {out}")
