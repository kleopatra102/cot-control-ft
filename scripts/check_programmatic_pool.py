#!/usr/bin/env python3
"""Checks and draw for the programmatic rule pool (cotctl.sft.programmatic). Rerun `pairs` and `bundles` for every model
whose traces are laid out differently (Gemma writes indented bullets) before building its training set.

    # 1. each rule alone, then every pair, on real traces of the model
    python scripts/check_programmatic_pool.py pairs   --rollouts results/r1llama/sft/stage1_rollouts.jsonl --out-dir results/r1llama/prog_pool
    # 2. every bundle of 5, 6 and 7 training rules, all rules applied together
    python scripts/check_programmatic_pool.py bundles --rollouts ... --out-dir ... --procs 14
    # 3. the balanced draw with questions
    python scripts/check_programmatic_pool.py draw    --rollouts ... --out-dir ... --n 900
    # 4. verify the draw on the model's own traces and write the stamp the build requires (also after any change to the rule code)
    python scripts/check_programmatic_pool.py verify  --rollouts ... --out-dir ...

    # all four in one go, for a new model:
    python scripts/check_programmatic_pool.py preflight --rollouts ... --out-dir ... --mt-cache .../mt_cache.json --translate --procs 14

Language rules are included when --mt-cache points to translations of the test traces (built here with --translate).
"""
from __future__ import annotations
import argparse, itertools, json, os, pickle, random, sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "src"))
from cotctl.sft import programmatic as G

N_TEST = 80; SEED_TRACES = 0
S: dict = {}                                    # shared with worker processes (fork)


def load(a):
    src = [json.loads(l) for l in open(a.rollouts)]
    src = [r for r in src if r.get("think_status") == "ok" and (r.get("reasoning") or "").strip()]
    random.seed(SEED_TRACES); S["src"] = src; S["traces"] = random.sample(src, min(N_TEST, len(src)))
    S["mt"] = None
    if a.mt_cache:
        from cotctl.sft.translate import Translator
        S["mt"] = Translator(a.mt_cache, protect=not a.no_protect)
        if a.translate:
            for lg in ("es", "fr", "ru", "pl"): S["mt"].many([r["reasoning"] for r in S["traces"][:50]], lg)
    S["langs"] = G.LANGS if S["mt"] else []
    S["all"] = [c for c in G.ALL if not c.startswith("lang:")] + S["langs"]


def run(bundle, r):
    """apply and grade one bundle on one trace -> list of failing rules, or None if a translation is missing"""
    lg = next((c.split(":")[1] for c in bundle if c.startswith("lang:")), None); rr = r
    if lg:
        k = S["mt"].key(r["reasoning"], lg)
        if k not in S["mt"].cache: return None
        rr = {"prompt": r["prompt"], "reasoning": S["mt"].cache[k]}
    t, args = G.apply([c for c in bundle if not c.startswith("lang:")], rr, lang=lg or "en")
    return G.grade_all(bundle, t, args, G.question(r))


def check(bundle, n, off=0):
    """Share of traces on which every rule passes. A trace on which a rule of the bundle fails even alone is left out
    (for example a case rule on a trace written partly in Japanese): the trace is unsuited, not the bundle."""
    ok = tot = 0; fails = Counter(); skip = set().union(*(S.get("alone_fail", {}).get(c, set()) for c in bundle)) if S.get("alone_fail") else set()
    for i, r in enumerate(S["traces"][off:off + n], off):
        if i in skip: continue
        try: f = run(bundle, r)
        except Exception: f = ["EXC"]
        if f is None: continue
        tot += 1; ok += not f; fails.update(f)
    return (ok / tot if tot else 0.0), fails


def cmd_pairs(a):
    load(a); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    single = {}; alone = {}
    for c in S["all"]:
        single[c] = check([c], 30)[0]; alone[c] = set()
        for i, r in enumerate(S["traces"][:50]):
            try: f = run([c], r)
            except Exception: f = ["EXC"]
            if f: alone[c].add(i)
    S["alone_fail"] = {c: v for c, v in alone.items() if single[c] >= 0.9}       # only rules that are otherwise fine
    print("rules passing alone on fewer than all 30 traces:", {c: round(v, 2) for c, v in single.items() if v < 1})
    good = [c for c in S["all"] if single[c] >= 0.9]; pair = {}
    for x, y in itertools.combinations(good, 2):
        pair[(x, y)] = check([x, y], 30)[0] if G.allowed(x, y) else -1.0
    okp = {k for k, v in pair.items() if v >= 0.99}
    print(f"rules {len(good)}; compatible pairs {len(okp)} of {len(pair)}; excluded with a reason {sum(v < 0 for v in pair.values())}; failing the test {sum(0 <= v < .99 for v in pair.values())}")
    pickle.dump((good, okp, single, pair, S["alone_fail"]), open(out / "pairs.pkl", "wb"))


def _work(chunk): return [(c, check([S["train"][i] for i in c], S["nt"], off=30)[0] == 1.0) for c in chunk]


def cmd_bundles(a):
    load(a); out = Path(a.out_dir); good, okp, single, pair, S["alone_fail"] = pickle.load(open(out / "pairs.pkl", "rb"))
    train = [c for c in good if c in G.TRAIN]; ix = {c: i for i, c in enumerate(train)}; adj = [0] * len(train)
    for x, y in okp:
        if x in ix and y in ix: adj[ix[x]] |= 1 << ix[y]; adj[ix[y]] |= 1 << ix[x]
    def enum(cur, cand, k, acc):
        if k == 0: acc.append(tuple(cur)); return
        while cand:
            v = cand.bit_length() - 1; cand &= ~(1 << v); enum(cur + [v], cand & adj[v], k - 1, acc)
    S["train"] = train; S["nt"] = a.traces; res = {}; L = {i for i, c in enumerate(train) if c.startswith("lang:")}
    with Pool(a.procs) as p:
        for k in a.k:
            allc = []; enum([], (1 << len(train)) - 1, k, allc); done = []
            for o in p.imap_unordered(_work, [allc[i:i + 400] for i in range(0, len(allc), 400)]): done.extend(o)
            res[k] = done; v = [c for c, ok in done if ok]
            print(f"k={k}: every pair compatible {len(done):,}; all rules pass on all {a.traces} traces {len(v):,} (no language {sum(not L & set(c) for c in v):,}; with a language {sum(bool(L & set(c)) for c in v):,})", flush=True)
    pickle.dump((train, res), open(out / "bundles.pkl", "wb"))


def cmd_draw(a):
    """Balanced draw: half the rows with 6 constraints and half with 7; a language rule in `lang_share` of rows, five languages in
    equal shares with English among them; each word separator in at most `sep_share` of rows; a bundle used at most `reuse` times."""
    load(a); out = Path(a.out_dir); rules, res = pickle.load(open(out / "bundles.pkl", "rb")); ix = {c: i for i, c in enumerate(rules)}
    L = {i for i, c in enumerate(rules) if c.startswith("lang:")}; inc = {ix[c] for c in G.INSERTS if c in ix}; SEP = {ix[c] for c in ("word_sep_pipe", "double_space") if c in ix}
    N = a.n; SEP_CAP = int(N * a.sep_share); V = {k: [c for c, ok in res[k] if ok] for k in res}
    en = {k: [c for c in V[k] if not L & set(c)] for k in V}; lg = {k: [c for c in V[k] if L & set(c)] for k in V}
    random.seed(a.seed); use = Counter(); reuse = Counter(); lang_use = Counter()
    def draw(pool, n, kind, extra):
        rows = []
        for _ in range(n):
            cand = [c for c in random.sample(pool, min(1500, len(pool))) if reuse[c] < a.reuse and all(use[i] < SEP_CAP for i in SEP & set(c))]
            if kind == "lang":
                lo = min(lang_use[i] for i in L); cand = [c for c in cand if lang_use[next(i for i in c if i in L)] == lo] or cand
            b = min(cand, key=lambda c: (sum(use[i] ** 2 for i in c if i not in L) / len([i for i in c if i not in L]), len(inc & set(c))))
            reuse[b] += 1; use.update(i for i in b if i not in L); lang_use.update(i for i in b if i in L)
            rows.append(dict(kind=kind, constraints=len(b) + extra, rules=[rules[i] for i in b] + (["lang:en"] if extra else []), inserts=len(inc & set(b))))
        return rows
    n_lang = int(N * a.lang_share); n_en_lang = n_lang // 5; n_tr = n_lang - n_en_lang; n_plain = N - n_lang
    rows = (draw(en[6], n_plain // 2, "plain", 0) + draw(en[7], n_plain - n_plain // 2, "plain", 0) + draw(lg[6], n_tr // 2, "lang", 0) + draw(lg[7], n_tr - n_tr // 2, "lang", 0)
            + draw(en[5], n_en_lang // 2, "lang_en", 1) + draw(en[6], n_en_lang - n_en_lang // 2, "lang_en", 1))
    random.shuffle(rows); src = random.Random(a.question_seed).sample(S["src"], N); final = []
    # a rule with several instruction wordings: each row takes one wording at random (all caps has three, all lowercase two).
    # For a row that needs no translation the wording is checked on the row's own trace, because the wordings have different graders.
    wordings = {}
    for alt, canon in G.DUPW.items():
        if alt not in G.HELD: wordings.setdefault(canon, [canon]).append(alt)
    wuse = Counter()
    for i, (d, r) in enumerate(zip(rows, src)):
        rl = list(d["rules"]); rw = random.Random(f"{a.question_seed}:{i}:wording")
        for j, c in enumerate(rl):
            if c in wordings:
                opts = wordings[c][:]; rw.shuffle(opts); pick = opts[0]
                if d["kind"] != "lang":
                    for o in opts:
                        b = [x for x in rl[:j] + [o] + rl[j + 1:] if not x.startswith("lang:")]
                        try: t, args = G.apply(b, r); good = not G.grade_all(b, t, args, G.question(r))
                        except Exception: good = False
                        if good: pick = o; break
                rl[j] = pick; wuse[pick] += 1
        random.Random(f"{a.question_seed}:{i}").shuffle(rl)
        final.append(dict(row=i, sample_id=r["sample_id"], kind=d["kind"], constraints=d["constraints"], inserts=d["inserts"], rules=rl, question=G.question(r)))
    json.dump(dict(version=a.version, seed=a.question_seed, rows=final), open(out / "draw.json", "w"), indent=0)
    u = sorted((use[i], rules[i]) for i in range(len(rules)) if i not in L)
    print(f"rows {N}; distinct bundles {len(reuse)}; constraints {sorted(Counter(r['constraints'] for r in final).items())}; language rows {sum(r['kind'] != 'plain' for r in final)}")
    print("rule usage: least", u[:4], "| most", u[-4:]); print("wordings used:", dict(wuse)); print(f"-> {out / 'draw.json'}")


# thresholds for the automatic verdict; a failure means "look at this before training", not "impossible"
MIN_BUNDLES = 1000        # valid bundles of 6 and of 7
MIN_TRAIN_RULES = 30      # training rules that appear in at least one valid bundle
MAX_ROW_FAIL = 0.02       # share of untranslated draw rows that fail a grader on their own trace
MAX_UNUSABLE = 0.05       # share of the model's traces that are unclosed or empty
MIN_LANG_OK = 0.9         # share of test traces whose translation passes the language grader


def cmd_verify(a, quiet=False):
    """Fast check of an existing draw against the model's own traces with the current code, and the stamp the build requires.
    Run it after any change to the rule code. For a new model run `preflight` instead."""
    load(a); out = Path(a.out_dir); draw_path = out / "draw.json"; d = json.load(open(draw_path)); fails = []; notes = []
    allrows = [json.loads(l) for l in open(a.rollouts)]; src = {r["sample_id"]: r for r in allrows}
    unusable = sum(1 for r in allrows if r.get("think_status") != "ok" or not (r.get("reasoning") or "").strip()) / max(1, len(allrows))
    notes.append(f"traces: {len(allrows)}; unusable (unclosed or empty) {unusable:.1%}")
    if unusable > MAX_UNUSABLE: fails.append(f"{unusable:.1%} of the traces are unusable (limit {MAX_UNUSABLE:.0%})")
    alone = {c: check([c], 30)[0] for c in S["all"] if c in G.TRAIN}
    low = {c: round(v, 2) for c, v in alone.items() if v < 1}
    notes.append("training rules that fail alone on some of 30 test traces: " + (json.dumps(low) if low else "none"))
    for c, v in low.items():
        if v < 0.9 and not c.startswith("lang:"): fails.append(f"rule {c} passes alone on only {v:.0%} of traces: its transform or grader does not fit this model's layout")
    if S["langs"]:
        for lg in S["langs"]:
            have = sum(S["mt"].key(r["reasoning"], lg.split(":")[1]) in S["mt"].cache for r in S["traces"][:30])
            if have < 30: fails.append(f"{lg}: {30 - have} of 30 test traces have no translation from the current translator; run again with --translate")
            elif alone.get(lg, 1) < MIN_LANG_OK: fails.append(f"{lg}: only {alone[lg]:.0%} of translated test traces pass the language grader")
    else: notes.append("language rules not checked (no --mt-cache)")
    bad = Counter(); n = miss = 0; used = Counter()
    for row in d["rows"]:
        r = src.get(row["sample_id"]); used.update(row["rules"])
        if r is None or r.get("think_status") != "ok" or not (r.get("reasoning") or "").strip(): miss += 1; continue
        if G.question(r).strip() != row["question"].strip(): fails.append(f"row {row['row']}: question differs from the trace"); continue
        if row["kind"] == "lang": continue
        b = [c for c in row["rules"] if not c.startswith("lang:")]
        try: t, args = G.apply(b, r); f = G.grade_all(b, t, args, row["question"])
        except Exception as e: f = [f"error {type(e).__name__}"]
        n += 1; bad.update(f[:1])
    notes.append(f"draw rows: {len(d['rows'])}; without a usable trace {miss}; untranslated rows built and graded {n}; failing {sum(bad.values())} {dict(bad) if bad else ''}")
    if miss: fails.append(f"{miss} draw rows have no usable trace for this model")
    if n and sum(bad.values()) / n > MAX_ROW_FAIL: fails.append(f"{sum(bad.values())} of {n} untranslated rows fail a grader (limit {MAX_ROW_FAIL:.0%})")
    stray = sorted(c for c in used if c != "lang:en" and c not in G.TRAIN and c not in G.DUPW)
    if stray: fails.append(f"the draw uses rules that are not training rules: {stray}")
    if (out / "bundles.pkl").exists():
        train, res = pickle.load(open(out / "bundles.pkl", "rb"))
        for k in (6, 7):
            v = [c for c, ok in res.get(k, []) if ok]; rules_in = {i for c in v for i in c}
            notes.append(f"valid bundles of {k}: {len(v):,}, using {len(rules_in)} rules")
            if len(v) < MIN_BUNDLES: fails.append(f"only {len(v)} valid bundles of {k} rules (limit {MIN_BUNDLES})")
            if k == 6 and len(rules_in) < MIN_TRAIN_RULES: fails.append(f"only {len(rules_in)} training rules appear in a valid bundle (limit {MIN_TRAIN_RULES})")
    else: fails.append("no bundles.pkl: the pair and bundle checks have not been run for this model")
    stamp = dict(passed=not fails, failures=fails, notes=notes, draw_sha=G.file_sha(draw_path), rollouts_sha=G.file_sha(a.rollouts), code_sha=G.code_sha(),
                 rollouts=str(a.rollouts), draw_version=d.get("version"), checked=__import__("datetime").datetime.now().isoformat(timespec="seconds"))
    json.dump(stamp, open(out / "check.json", "w"), indent=1)
    rep = ["# Pool check for " + str(a.rollouts), "", "Result: **" + ("PASS" if not fails else "FAIL") + "**", ""] + ["- " + x for x in notes]
    if fails: rep += ["", "## Problems to fix before building", ""] + ["- " + x for x in fails]
    rep += ["", "## What to do", "",
            "- PASS: build with scripts/build_sft_programmatic.py, then read about 20 built rows (its --inspect-md option writes them to a file).",
            "- A rule fails alone: look at one failing trace; the model's layout (bullets, tables, another language) usually breaks an assumption of the transform. Fix it in src/cotctl/sft/programmatic.py or move the rule to HELD, then run preflight again.",
            "- Few bundles or many failing rows: run preflight again after the fix; never build from a draw that was checked on another model's traces."]
    open(out / "PREFLIGHT.md", "w").write("\n".join(rep) + "\n")
    if not quiet: print("\n".join(rep))
    return 0 if not fails else 1


def cmd_preflight(a):
    """Everything a new model needs, in order: each rule alone and every pair, every bundle of 5, 6 and 7, the draw, then verify."""
    print("== 1/4 rules alone and in pairs", flush=True); cmd_pairs(a)
    print("== 2/4 bundles", flush=True); cmd_bundles(a)
    print("== 3/4 draw", flush=True); cmd_draw(a)
    print("== 4/4 verify", flush=True); return cmd_verify(a)


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    def add(name, fn):
        p = sub.add_parser(name); p.set_defaults(fn=fn); p.add_argument("--rollouts", required=True); p.add_argument("--out-dir", required=True)
        p.add_argument("--mt-cache", default=None); p.add_argument("--translate", action="store_true"); p.add_argument("--no-protect", action="store_true"); return p
    add("pairs", cmd_pairs)
    p = add("bundles", cmd_bundles); p.add_argument("--k", type=int, nargs="+", default=[5, 6, 7]); p.add_argument("--procs", type=int, default=8); p.add_argument("--traces", type=int, default=20)
    p = add("draw", cmd_draw); p.add_argument("--n", type=int, default=900); p.add_argument("--seed", type=int, default=0); p.add_argument("--question-seed", type=int, default=20261124)
    p.add_argument("--lang-share", type=float, default=0.30); p.add_argument("--sep-share", type=float, default=0.10); p.add_argument("--reuse", type=int, default=3); p.add_argument("--version", default="draw")
    add("verify", cmd_verify)
    p = add("preflight", cmd_preflight); p.add_argument("--k", type=int, nargs="+", default=[5, 6, 7]); p.add_argument("--procs", type=int, default=8); p.add_argument("--traces", type=int, default=20)
    p.add_argument("--n", type=int, default=900); p.add_argument("--seed", type=int, default=0); p.add_argument("--question-seed", type=int, default=20261124)
    p.add_argument("--lang-share", type=float, default=0.30); p.add_argument("--sep-share", type=float, default=0.10); p.add_argument("--reuse", type=int, default=3); p.add_argument("--version", default="draw")
    a = ap.parse_args(); raise SystemExit(a.fn(a) or 0)


if __name__ == "__main__": main()
