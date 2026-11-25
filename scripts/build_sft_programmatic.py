#!/usr/bin/env python3
"""Build a controllability training set with programmatic rules only (no LLM edit of the target).

Each row of the draw names a source trace, its rules in prompt order and its question. For every row:
    source trace -> [remarks about the rules, from the remark step] -> [translation, for a language row] -> code rules -> exact graders
A row is written only if every grader passes.

    python scripts/build_sft_programmatic.py --draw results/r1qwen7/prog_pool/draw.json \
        --rollouts results/r1qwen7/sft/stage1_rollouts.jsonl --out-dir results/r1qwen7/build_prog --data-prefix q7prog \
        [--remarks-build results/r1qwen7/remarks/build.json] [--mt-cache results/r1qwen7/build_prog/mt_cache.json] [--tokenizer deepseek-ai/DeepSeek-R1-Distill-Qwen-7B]

--remarks-build: output of the remark step. Its text with remarks (already translated for language rows) is taken as the
                 input to the code rules; this script applies the rules again and grades independently.
--control:       also write the control arm: the same questions with the unedited source trace and a prompt without rules.
"""
from __future__ import annotations
import argparse, hashlib, json, re, statistics as st, sys
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.sft import programmatic as G
from cotctl.sft import pool as P
from cotctl.sft.build import TrainingRow, write_training_jsonl
from cotctl.prompts import reasonif_multi_prompt, reasonif_baseline_prompt

REAL = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")


def measure(text: str, tok) -> dict:
    return {"tokens_by_space": len(text.split()), "words": len(REAL.findall(text)), "chars": len(text), **({"model_tokens": len(tok(text).input_ids)} if tok else {})}


def summary(vals: list[dict]) -> dict:
    if not vals: return {}
    out = {}
    for k in vals[0]:
        v = sorted(x[k] for x in vals); q = st.quantiles(v, n=4) if len(v) > 1 else [v[0]] * 3
        out[k] = {"median": st.median(v), "q1": q[0], "q3": q[2]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draw", required=True); ap.add_argument("--rollouts", required=True); ap.add_argument("--out-dir", required=True)
    ap.add_argument("--data-prefix", required=True); ap.add_argument("--arm", default="Bp")
    ap.add_argument("--remarks-build", default=None); ap.add_argument("--mt-cache", default=None); ap.add_argument("--no-protect", action="store_true")
    ap.add_argument("--tokenizer", default=None); ap.add_argument("--control", action="store_true"); ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip-pool-check", action="store_true", help="build although the draw has no matching check stamp (only for debugging)")
    ap.add_argument("--inspect-md", default=None, help="write this many randomly chosen built rows to a markdown file for reading"); ap.add_argument("--inspect-n", type=int, default=24)
    a = ap.parse_args(); out_dir = Path(a.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    probs = G.stamp_problems(a.draw, a.rollouts)
    if probs:
        print("This draw has not been checked for these traces with the current rule code:"); [print("  -", x) for x in probs]
        print("Run: python scripts/check_programmatic_pool.py verify --rollouts", a.rollouts, "--out-dir", Path(a.draw).parent,
              "\n(for a new model: the same with `preflight`). See PROGRAMMATIC_RULES_NEW_MODEL.md.")
        if not a.skip_pool_check: return 2
        print("--skip-pool-check given: building anyway.")
    draw = json.load(open(a.draw)); plan = draw["rows"][: a.limit] if a.limit else draw["rows"]
    src = {r["sample_id"]: r for r in map(json.loads, open(a.rollouts))}
    remarks = {r["row"]: r for r in json.load(open(a.remarks_build))} if a.remarks_build else {}
    tok = None
    if a.tokenizer:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(a.tokenizer)
    mt = None
    def translator():
        nonlocal mt
        if mt is None:
            from cotctl.sft.translate import Translator
            mt = Translator(a.mt_cache or out_dir / "mt_cache.json", protect=not a.no_protect)
        return mt
    rows, ctrl, dropped = [], [], []; differs, n_remark, rem_words = [], [], []; fails = Counter(); drawn = Counter(); kept = Counter(); how = Counter(); L_src, L_tgt, by_kind = [], [], {}
    for d in plan:
        r = src.get(d["sample_id"])
        if r is None or not (r.get("reasoning") or "").strip(): dropped.append({"row": d["row"], "reason": "source trace missing"}); fails["source missing"] += 1; continue
        q = G.question(r)
        if q.strip() != d["question"].strip(): dropped.append({"row": d["row"], "reason": "question differs from the draw"}); fails["question differs"] += 1; continue
        rules = d["rules"]; code_rules = [c for c in rules if not c.startswith("lang:")]; lg = next((c.split(":")[1] for c in rules if c.startswith("lang:")), None)
        drawn.update(rules)
        # rule parameters and the prompt are fixed from the source trace, before remarks and translation
        a_src = P.finish_args([c for c in P.CONDS if c in code_rules], {}, q, r["reasoning"]); ins = [G.instruction(c, a_src) for c in rules]
        rm = remarks.get(d["row"]); spans = None
        if remarks:
            # with a remark build, a row is used only if the remark step finished it for exactly this row; a row whose base
            # trace could not be measured has no remark profile and is left out, not built without remarks
            if not rm or rm.get("status") != "ok" or rm.get("rules") != rules or rm.get("sample_id") != d["sample_id"] or not rm.get("before_rules"):
                fails["not finished by the remark step"] += 1; dropped.append({"row": d["row"], "reason": "remark step: " + str((rm or {}).get("status", "row missing"))[:160]}); continue
            text = rm["before_rules"]; spans = [tuple(x) for x in rm.get("remark_spans") or []] or None
            how["with remarks" if spans else "no remark in the base trace"] += 1
        else:
            text = r["reasoning"]; how["without the remark step"] += 1
            if lg and lg != "en": text = translator().one(text, lg)
        try: t, args = G.apply(code_rules, {"prompt": r["prompt"], "reasoning": text}, keep_clear=spans)
        except Exception as e: dropped.append({"row": d["row"], "reason": f"transform error {type(e).__name__}: {e}"}); fails["transform error"] += 1; continue
        bad = G.grade_all(rules, t, args, q)
        if spans: bad += ["used only inside a remark: " + c for c in G.real_use_problems(code_rules, {"prompt": r["prompt"], "reasoning": text}, spans)]
        if [G.instruction(c, args) for c in rules] != ins: bad.append("instruction parameters changed after remarks or translation")
        if rm and rm.get("output") is not None and rm["output"] != t: differs.append(d["row"])     # the remark step applied the rules itself; both must agree
        if bad: fails.update(bad); dropped.append({"row": d["row"], "rules": rules, "failed": bad, "text": t[:600]}); continue
        n_remark.append(len(spans or [])); rem_words.append(sum(len(text[x:y].split()) for x, y in (spans or [])))
        kept.update(rules); ms, mt_ = measure(r["reasoning"], tok), measure(t, tok); L_src.append(ms); L_tgt.append(mt_); by_kind.setdefault(d["kind"], []).append((ms, mt_))
        qid = hashlib.sha256(q.encode()).hexdigest()[:16]
        rows.append(TrainingRow(row_idx=d["row"], question_id=qid, mode="+".join(rules), prompt=reasonif_multi_prompt(q, ins), reasoning=t, answer=(r.get("answer") or "").strip(),
                                constraint_args={**args, "constraints": rules, "sample_id": d["sample_id"], "language": lg or "en"}))
        ctrl.append(TrainingRow(row_idx=d["row"], question_id=qid, mode="control", prompt=reasonif_baseline_prompt(q), reasoning=r["reasoning"], answer=(r.get("answer") or "").strip(),
                                constraint_args={"sample_id": d["sample_id"]}))
    if a.inspect_md and rows:
        import random
        srcmap = {d["row"]: src[d["sample_id"]] for d in plan if d["sample_id"] in src}
        md = [f"# Built rows to read ({a.data_prefix}_{a.arm})", "", f"{min(a.inspect_n, len(rows))} rows chosen at random from {len(rows)} built rows. Each passed all of its graders.", ""]
        fence = lambda x: "~~~~text\n" + x.replace("~~~~", "~~~ ~").rstrip("\n") + "\n~~~~"
        for x in random.Random(0).sample(rows, min(a.inspect_n, len(rows))):
            md += [f"## Row {x.row_idx}", "", "### Rules: " + ", ".join(x.constraint_args["constraints"]), "", "### Prompt", "", fence(x.prompt), "",
                   "### Source trace", "", fence(srcmap[x.row_idx]["reasoning"]), "", "### Training target", "", fence(x.reasoning), ""]
        Path(a.inspect_md).parent.mkdir(parents=True, exist_ok=True); open(a.inspect_md, "w").write("\n".join(md))
    dry = "_dry" if a.limit else ""
    out = write_training_jsonl(rows, REPO / f"data/sft/{a.data_prefix}_{a.arm}{dry}.jsonl")
    if a.control: write_training_jsonl(ctrl, REPO / f"data/sft/{a.data_prefix}_{a.arm}ctrl{dry}.jsonl")
    stats = {"draw": a.draw, "draw_version": draw.get("version"), "planned": len(plan), "kept": len(rows), "how": dict(how), "failures": dict(fails),
             "remarks": {"rows_with_a_remark": sum(1 for x in n_remark if x), "remark_sentences": sum(n_remark), "median_remark_words_in_rows_with_remarks": (st.median([w for w in rem_words if w]) if any(rem_words) else 0),
                         "rows_where_output_differs_from_the_remark_step": differs[:50]},
             "length_source": summary(L_src), "length_target": summary(L_tgt),
             "length_by_kind": {k: {"rows": len(v), "source": summary([x for x, _ in v]), "target": summary([y for _, y in v])} for k, v in by_kind.items()},
             "per_rule": {c: {"drawn": drawn[c], "kept": kept[c]} for c in sorted(drawn)}, "dropped_rows": dropped[:300]}
    json.dump(stats, open(out_dir / f"{a.arm}_stats{dry}.json", "w"), ensure_ascii=False, indent=1)
    print(f"kept {len(rows)} / {len(plan)} -> {out}   ({dict(how)})")
    if fails: print("failures:", dict(fails))
    if remarks: print(f"rows with a remark {sum(1 for x in n_remark if x)} / {len(rows)}; remark sentences {sum(n_remark)}; rows whose output differs from the remark step's own: {len(differs)}")
    for k in ("tokens_by_space", "words", "chars", "model_tokens"):
        if L_src and k in L_src[0]: print(f"  {k:16s} source median {stats['length_source'][k]['median']:.0f}   target median {stats['length_target'][k]['median']:.0f}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
