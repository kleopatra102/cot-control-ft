#!/usr/bin/env python3
"""Full-trace LLM meta-discussion labelling + strip-and-regrade, CoTControl and ReasonIF.

Stage A  one gpt-5-mini call per rollout (no character cap): every narration sentence, verbatim.
Stage B  two stripped variants per trace: `llm` (units matching an LLM sentence) and `regex`
         (units matching any of METR's seven patterns). No union.
Stage C  re-grade every condition, binary + continuous, on original / llm / regex.
         ignore_question: one count prompt (VIOLATING n / TOTAL m) per text -> binary (n==0) and
         continuous (1 - n/m); 3 calls per rollout (original, llm, regex).
Stage D  self-consistency: second independent labelling of --consistency N rollouts.
Per-rollout and per-unit records are written for the report script; nothing is aggregated here
beyond a console table.

    python scripts/strip_llm.py --labels base step-60 --suites cotcontrol reasonif [--per-mode-limit 1]
Single event loop, one LLMJudge, cache results/strip_llm/judge_cache.jsonl. PID in run.pid.
"""
from __future__ import annotations
import argparse, asyncio, json, os, re, statistics as st, sys, time, random
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from dotenv import load_dotenv; load_dotenv(REPO / ".env", override=True)
import importlib.util
spec = importlib.util.spec_from_file_location("sr", REPO / "scripts/strip_regrade.py"); sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)
from cotctl.graders.cotcontrol import grade_cotcontrol, detect_meta_discussion, _META_PATTERNS
from cotctl.graders.continuous import count_keyword_uses
from cotctl.graders.continuous_v2 import score_v2, score_ignore_question
from cotctl.graders.reasonif import grade_reasonif, count_words
from cotctl.graders.continuous_reasonif import score_reasonif
from cotctl.judge import LLMJudge
OUT = REPO / "results/strip_llm"; OUT.mkdir(parents=True, exist_ok=True)
PATS = [(p, re.compile(p)) for p in _META_PATTERNS]

def norm(s: str) -> str: return re.sub(r"\s+", " ", s).strip().lower()
def load(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []

def unit_table(text: str, sents: list[str]) -> list[dict]:
    """One record per sentence unit: text, char offset, llm-marked?, regex patterns hit."""
    ns = [norm(x) for x in sents if len(norm(x)) >= 12]
    out, pos = [], 0
    for u in sr.split_keep(text):
        nu = norm(u)
        llm = bool(nu) and any(v in nu or (len(nu) >= 60 and nu in v) for v in ns)
        pats = [name for name, rx in PATS if rx.search(u.lower())]
        out.append({"start": pos, "len": len(u), "llm": llm, "regex": pats, "text": u})
        pos += len(u)
    return out

def rebuild(units, drop_key) -> str:
    return "".join(u["text"] for u in units if not u[drop_key])

def grade(suite, mode, text, kws, args, unc):
    """(binary or None, continuous or None); ignore_question handled by the judge elsewhere."""
    if suite == "cotcontrol":
        if mode == "ignore_question": return None, None
        return grade_cotcontrol(mode, text, keywords=kws), score_v2(mode, text, keywords=kws, unconstrained_uses=unc)
    return grade_reasonif(mode, text, args), score_reasonif(mode, text, args)

async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", nargs="+", default=["base", "step-60"])
    ap.add_argument("--suites", nargs="+", default=["cotcontrol", "reasonif"])
    ap.add_argument("--per-mode-limit", type=int, default=None, help="rollouts per (label, suite, mode)")
    ap.add_argument("--limit-labels", nargs="*", default=None, help="apply --per-mode-limit only to these labels")
    ap.add_argument("--skip-iq", action="store_true", help="skip the ignore_question count calls")
    ap.add_argument("--max-retries", type=int, default=6)
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--consistency", type=int, default=50, help="rollouts relabelled a second time (cotcontrol base)")
    ap.add_argument("--model", default=os.environ.get("JUDGE_MODEL", "gpt-5-mini"))
    ap.add_argument("--cache-model", default="gpt-5-mini", help="model name used in cache keys (keep gpt-5-mini when switching endpoints)")
    a = ap.parse_args()
    (OUT / "run.pid").write_text(str(os.getpid()))
    judge = LLMJudge(model=a.model, cache_path=OUT / "judge_cache.jsonl", concurrency=a.concurrency, max_retries=a.max_retries, cache_model=a.cache_model)
    print(f"judge {a.model} @ {judge.base_url}  pid {os.getpid()}", flush=True)
    capped = {(v["label"], v["suite"], v["sample_id"], v["mode"]): v for v in load(REPO / "results/meta_judge/meta_verdicts.jsonl")}
    console = []
    for label in a.labels:
        for suite in a.suites:
            t0 = time.time()
            rows = [r for r in load(REPO / f"results/{label}/{suite}_rollouts.jsonl") if not r.get("error") and r.get("think_status") == "ok" and r.get("reasoning")]
            if a.per_mode_limit and (not a.limit_labels or label in a.limit_labels):
                seen = defaultdict(int); keep = []
                for r in rows:
                    if seen[r["mode"]] < a.per_mode_limit: keep.append(r); seen[r["mode"]] += 1
                rows = keep
            if not rows: print(f"[{label}/{suite}] no rollouts", flush=True); continue
            graded = {g["sample_id"]: g for g in load(REPO / f"results/{label}/graded_{label}_{suite}.jsonl")}
            unc = {}
            if suite == "cotcontrol":
                kw = {r["sample_id"]: r["meta"].get("keywords") or [] for r in rows if r["mode"] in sr.SUPP}
                unc = {r["sample_id"]: count_keyword_uses(r.get("reasoning") or "", kw[r["sample_id"]])
                       for r in load(REPO / f"results/{label}/unconstrained_rollouts.jsonl") if r["sample_id"] in kw and r.get("think_status") == "ok"}
            # ---- Stage A
            print(f"[{label}/{suite}] stage A: {len(rows)} rollouts", flush=True)
            verd = await judge.judge_many("narration_full", [(r["prompt"], r["reasoning"]) for r in rows], desc=f"{label}/{suite} A")
            errs = sum(v.error is not None for v in verd); print(f"[{label}/{suite}] stage A: {errs} errors, {time.time()-t0:.0f}s", flush=True)
            # ---- Stage B+C
            recs, iq = [], []
            for r, v in zip(rows, verd):
                m, t = r["mode"], r["reasoning"]; kws = r["meta"].get("keywords") or []; args = r["meta"].get("constraint_args") or {}
                sents = json.loads(v.detail) if v.detail else []
                units = unit_table(t, sents)
                texts = {"original": t, "llm": rebuild(units, "llm"), "regex": rebuild(units, "regex")}
                g = graded.get(r["sample_id"], {})
                cap = capped.get((label, suite, r["sample_id"], m), {})
                rec = {"label": label, "suite": suite, "mode": m, "sample_id": r["sample_id"], "chars": len(t), "words": count_words(t),
                       "n_units": len(units), "llm_error": v.error, "llm_sentences": sents, "n_llm_sentences": len(sents),
                       "n_llm_units": sum(u["llm"] for u in units), "n_regex_units": sum(bool(u["regex"]) for u in units),
                       "llm_meta": bool(v.compliant) if v.error is None else None, "regex_meta": detect_meta_discussion(t),
                       "capped_judge_meta": cap.get("llm_meta"), "capped_judge_quotes": cap.get("llm_violations"),
                       "first_llm_pos": next((u["start"] / len(t) for u in units if u["llm"]), None),
                       "last_llm_pos": next((u["start"] / len(t) for u in reversed(units) if u["llm"]), None),
                       "removed": {k: 1 - len(x) / len(t) for k, x in texts.items()},
                       "correct": g.get("correct"), "bin_graded_original": g.get("compliant"),
                       "units": [{"start": u["start"], "len": u["len"], "llm": u["llm"], "regex": u["regex"]} for u in units if u["llm"] or u["regex"]],
                       "scores": {}}
                for k, x in texts.items():
                    b, c = grade(suite, m, x, kws, args, unc.get(r["sample_id"]))
                    rec["scores"][k] = {"binary": b, "continuous": c}
                if suite == "cotcontrol" and m == "ignore_question": iq.append((rec, r["prompt"], texts))
                recs.append(rec)
            # ---- ignore_question via count prompt
            if iq and a.skip_iq:
                print(f"[{label}/{suite}] ignore_question: count calls skipped (--skip-iq)", flush=True)
            elif iq:
                print(f"[{label}/{suite}] ignore_question: {len(iq)} rollouts x 3 count calls", flush=True)
                items = [(p, texts[k]) for rec, p, texts in iq for k in ("original", "llm", "regex")]
                cv = await judge.judge_many("ignore_count", items, desc=f"{label} iq count")
                for i, (rec, p, texts) in enumerate(iq):
                    for j, k in enumerate(("original", "llm", "regex")):
                        v = cv[3 * i + j]
                        if v.detail:
                            d = json.loads(v.detail); rec["scores"][k] = {"binary": d["violating"] == 0, "continuous": score_ignore_question(d["violating"], d["total"]), "count": d}
                        else:
                            rec["scores"][k] = {"binary": None, "continuous": None, "error": v.error}
            with open(OUT / f"rollouts_{label}_{suite}.jsonl", "w", encoding="utf-8") as f:
                for rec in recs: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            # console summary
            by = defaultdict(list)
            for rec in recs: by[rec["mode"]].append(rec)
            for m, rs in sorted(by.items()):
                def mean(key, sc):
                    xs = [x["scores"][key][sc] for x in rs if x["scores"].get(key, {}).get(sc) is not None]
                    return (st.mean(xs) if xs else None), len(xs)
                bo, n = mean("original", "binary"); bl, _ = mean("llm", "binary"); br, _ = mean("regex", "binary")
                co, _ = mean("original", "continuous"); cl, _ = mean("llm", "continuous"); cr, _ = mean("regex", "continuous")
                f = lambda x, pct=False: "   —" if x is None else (f"{100*x:5.1f}" if pct else f"{x:5.3f}")
                console.append(f"{label:<8}{suite:<11}{m:<27}{n:>5} | bin {f(bo,1)} {f(bl,1)} {f(br,1)} | cont {f(co)} {f(cl)} {f(cr)} | llm-meta {100*st.mean(bool(x['llm_meta']) for x in rs):5.1f}%  regex {100*st.mean(x['regex_meta'] for x in rs):5.1f}%  rm-llm {100*st.mean(x['removed']['llm'] for x in rs):4.1f}%")
            print(f"[{label}/{suite}] done, {time.time()-t0:.0f}s", flush=True)
    # ---- Stage D: self-consistency on cotcontrol base
    if a.consistency:
        rows = [r for r in load(REPO / "results/base/cotcontrol_rollouts.jsonl") if not r.get("error") and r.get("think_status") == "ok" and r.get("reasoning")]
        rng = random.Random(0); pick = rng.sample(rows, min(a.consistency, len(rows)))
        print(f"[consistency] relabelling {len(pick)} base/cotcontrol rollouts", flush=True)
        v1 = await judge.judge_many("narration_full", [(r["prompt"], r["reasoning"]) for r in pick], desc="consistency s1")
        async def second(pr, rs): return await judge.narration_sentences(pr, rs, attempt=1)
        v2 = await asyncio.gather(*(second(r["prompt"], r["reasoning"]) for r in pick))
        with open(OUT / "consistency.jsonl", "w", encoding="utf-8") as f:
            for r, x, y in zip(pick, v1, v2):
                s1 = json.loads(x.detail) if x.detail else []; s2 = json.loads(y.detail) if y.detail else []
                f.write(json.dumps({"sample_id": r["sample_id"], "mode": r["mode"], "s1": s1, "s2": s2, "err": [x.error, y.error]}, ensure_ascii=False) + "\n")
    print("\nlabel   suite      mode                          n | binary% orig/llm/regex | continuous orig/llm/regex | narration rates")
    print("\n".join(console)); print("\nwrote results/strip_llm/rollouts_*.jsonl")
    return 0

if __name__ == "__main__": raise SystemExit(asyncio.run(main()))
