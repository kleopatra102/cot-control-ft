#!/usr/bin/env python3
"""Phase-2 (unlearning) datasets from the starting model's own unconstrained traces (UNLEARNING_PLAN.md).

U: CoTControl prompt with one of the unlearning modes (uniform per question) + the unconstrained trace, kept only if
   the CoTControl grader says the trace FAILS the mode (ignore_question is non-compliant by construction: the trace
   reasons about the question).
C: the plain question prompt + the same trace.

    python scripts/build_unlearn.py            # -> data/sft/unlearn_U.jsonl, data/sft/unlearn_C.jsonl, results/unlearn/build_stats.json
"""
from __future__ import annotations
import argparse, json, random, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.inference import RolloutStore
from cotctl.graders.cotcontrol import grade_cotcontrol
from cotctl.multi_eval import _cc_requirement, NO_RESTATE_MULTI
from cotctl.prompts import cotcontrol_control_value, REASONING_TERM
from cotctl.sft.build import TrainingRow, write_training_jsonl

UNLEARN_MODES = ("uppercase_thinking", "alternating_case", "word_suppression", "multiple_word_suppression", "repeat_sentences", "end_of_sentence", "meow_between_words", "ignore_question")
HELD_OUT_MODES = ("json_format", "lowercase_thinking")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--traces", default=str(REPO / "results/unlearn/traces.jsonl")); ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(); rng = random.Random(a.seed)
    rs = [r for r in RolloutStore(a.traces).read_all() if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip() and (r.get("answer") or "").strip()]
    rs.sort(key=lambda r: r["sample_id"]); rng.shuffle(rs)
    U, C, dropped, per_mode = [], [], [], Counter()
    for i, r in enumerate(rs):
        mode = UNLEARN_MODES[i % len(UNLEARN_MODES)]  # balanced assignment over a shuffled order
        kws = r["meta"].get("keywords") or []
        plain = r["prompt"]  # the stored prompt is the plain question prompt; the constrained one adds the CoTControl Requirement line (same text as the evaluation prompts)
        cons_prompt = f"{plain}\n\nRequirement: {_cc_requirement(mode, cotcontrol_control_value(mode, kws))}{NO_RESTATE_MULTI.format(reasoning_term=REASONING_TERM)}"
        trace = r["reasoning"].strip()
        compliant = False if mode == "ignore_question" else bool(grade_cotcontrol(mode, trace, keywords=kws))
        if compliant: dropped.append({"sample_id": r["sample_id"], "mode": mode}); per_mode[f"{mode}:dropped"] += 1; continue
        per_mode[mode] += 1; args = {"mode": mode, "keywords": kws}
        U.append(TrainingRow(row_idx=len(U), question_id=r["sample_id"], mode=mode, prompt=cons_prompt, reasoning=trace, answer=r["answer"].strip(), constraint_args=args))
        C.append(TrainingRow(row_idx=len(C), question_id=r["sample_id"], mode="unconstrained", prompt=plain, reasoning=trace, answer=r["answer"].strip(), constraint_args={"paired_mode": mode}))
    write_training_jsonl(U, REPO / "data/sft/unlearn_U.jsonl"); write_training_jsonl(C, REPO / "data/sft/unlearn_C.jsonl")
    stats = {"traces_ok": len(rs), "U": len(U), "C": len(C), "dropped_compliant": len(dropped), "per_mode": dict(per_mode), "dropped": dropped[:50]}
    json.dump(stats, open(REPO / "results/unlearn/build_stats.json", "w"), indent=1); print(json.dumps({k: v for k, v in stats.items() if k != "dropped"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
