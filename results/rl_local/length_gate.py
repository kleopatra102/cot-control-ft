"""Length gate before RL: is the treated arm's reasoning as long as the control arm's on the RL prompt, before any update?

length_gate.py --treated <train_samples.jsonl ...> --control <train_samples.jsonl ...> --lo <ratio> --hi <ratio> --out <json>

Reads only the step-0 completions of each run (sampled from the adapter as loaded, before the first update). The i-th
treated file is paired with the i-th control file (same seed), and the two must have drawn the same prompts.
ratio = median reasoning words (treated) / median reasoning words (control), pooled over the runs; words are
whitespace-separated. The gate passes when lo <= ratio <= hi. The band has no default: set it before the runs.
Also printed, not gated: the ratio per seed, a 95% interval from resampling prompts, completion tokens, truncations.
Exit status: 0 pass, 1 outside the band, 2 unusable input.
"""
import argparse
import json
import random
import statistics
import sys


def step0(path: str) -> list[dict]:
    try:
        rows = [r for r in map(json.loads, open(path)) if r["step"] == 0]
    except OSError as e:
        print(f"length gate: cannot read {path}: {e}"); sys.exit(2)
    if not rows:
        print(f"length gate: no step-0 completions in {path}"); sys.exit(2)
    return rows


def words(r: dict) -> int:
    return len((r["reasoning"] or "").split())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--treated", nargs="+", required=True); ap.add_argument("--control", nargs="+", required=True)
    ap.add_argument("--lo", type=float, required=True); ap.add_argument("--hi", type=float, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if len(a.treated) != len(a.control):
        print("length gate: give the same number of treated and control runs"); sys.exit(2)
    if not 0 < a.lo <= a.hi:
        print("length gate: need 0 < lo <= hi"); sys.exit(2)
    by_prompt: dict[tuple[int, str], tuple[list[dict], list[dict]]] = {}   # (run, prompt id) -> (treated, control)
    per_run = []
    for i, (tp, cp) in enumerate(zip(a.treated, a.control)):
        t, c = step0(tp), step0(cp)
        if sorted(r["id"] for r in t) != sorted(r["id"] for r in c):
            print(f"length gate: {tp} and {cp} did not draw the same step-0 prompts"); sys.exit(2)
        for arm, rows in ((0, t), (1, c)):
            for r in rows:
                by_prompt.setdefault((i, r["id"]), ([], []))[arm].append(r)
        per_run.append(round(statistics.median(map(words, t)) / statistics.median(map(words, c)), 3))

    def ratio(keys) -> float:
        t = [words(r) for k in keys for r in by_prompt[k][0]]
        c = [words(r) for k in keys for r in by_prompt[k][1]]
        return statistics.median(t) / statistics.median(c)

    keys = sorted(by_prompt)
    rng = random.Random(0)
    boot = sorted(ratio(rng.choices(keys, k=len(keys))) for _ in range(2000))
    T = [r for k in keys for r in by_prompt[k][0]]; C = [r for k in keys for r in by_prompt[k][1]]
    value = ratio(keys)
    res = {
        "pass": a.lo <= value <= a.hi, "ratio": round(value, 3), "band": [a.lo, a.hi],
        "ratio_95": [round(boot[50], 3), round(boot[1949], 3)], "ratio_per_run": per_run,
        "median_words": {"treated": statistics.median(map(words, T)), "control": statistics.median(map(words, C))},
        "median_completion_tokens": {"treated": statistics.median(r["tokens"] for r in T),
                                     "control": statistics.median(r["tokens"] for r in C)},
        "truncated": {"treated": sum(bool(r["truncated"]) for r in T), "control": sum(bool(r["truncated"]) for r in C)},
        "completions": {"treated": len(T), "control": len(C)}, "prompts": len(keys),
        "treated_runs": a.treated, "control_runs": a.control,
    }
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"length gate {'PASS' if res['pass'] else 'FAIL'}: treated/control median reasoning words "
          f"{res['median_words']['treated']:g} / {res['median_words']['control']:g} = {value:.2f} "
          f"(95% {boot[50]:.2f} to {boot[1949]:.2f}; per seed {per_run}); band {a.lo:g} to {a.hi:g}; "
          f"{len(keys)} prompts, {len(T)} + {len(C)} completions, truncated {res['truncated']['treated']} + "
          f"{res['truncated']['control']}")
    sys.exit(0 if res["pass"] else 1)


if __name__ == "__main__":
    main()
