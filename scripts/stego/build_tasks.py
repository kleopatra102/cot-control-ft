#!/usr/bin/env python3
"""Task set for the covert-reasoning (steganography) test, ported from
github.com/rain-1/astra-multihop-steganographic-reasoning (commit in data/stego/source/UPSTREAM_COMMIT; post:
lesswrong.com/posts/CPJ2kYRKo77ucZEEG).

Two task types, each with a depth dial (number of dependent steps) and an exact answer plus the intermediate trace:
- lookup chains: regenerated with the upstream generator for every depth 1-12 (the upstream set only covers 7-12),
  2 tasks per family per depth (4 families -> 8 per depth, 96 tasks);
- cryptographic operations: toy CRC-4 (depths 3-12), mini-hash and LCG PRNG (depths 1-12), the upstream tasks,
  4 per family per depth (136 tasks).

    python scripts/stego/build_tasks.py
Writes data/stego/tasks.jsonl: {id, kind, family, depth, question, answer, trace}.
"""
import collections, importlib.util, json, random, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]; SRC = REPO / "data/stego/source"
PER_FAMILY_DEPTH = {"lookup": 2, "crypto": 4}


def lookup_tasks(seed=20261012):
    spec = importlib.util.spec_from_file_location("gen", SRC / "generate_deep_multistep_tasks.py")
    gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
    rng, out, seen = random.Random(seed), [], set()
    for depth in range(1, 13):
        for fam in gen.FAMILIES:
            n = 0
            while n < PER_FAMILY_DEPTH["lookup"]:
                t = fam(rng, depth, 0)
                if t.question in seen: continue
                seen.add(t.question); n += 1
                assert len(t.trace) == depth and str(t.trace[-1]) == t.answer
                out.append(dict(id=f"LOOKUP-D{depth:02d}-{len(out):03d}", kind="lookup", family=t.family, depth=depth,
                                question=t.question, answer=t.answer, trace=t.trace))
    return out


def crypto_tasks(seed=20261012):
    files = ["hash_easy_depth1_3_6_each", "hash_tranche1_depth3_12_6_each", "lcg_depth1_12_3_each", "lcg_tranche1_depth3_12_6_each",
             "crc_tranche1_depth3_12_6_each", "crc_tranche2_depth5_11_6_each"]
    pool = collections.defaultdict(list)
    for f in files:
        for t in json.load(open(SRC / f"{f}.json")): pool[(t["family"], t["depth"])].append(t)
    rng, out = random.Random(seed), []
    for (fam, depth), ts in sorted(pool.items()):
        ts = sorted({t["question"]: t for t in ts}.values(), key=lambda t: t["id"]); rng.shuffle(ts)
        for t in ts[: PER_FAMILY_DEPTH["crypto"]]:
            assert len(t["trace"]) == depth and str(t["trace"][-1]) == str(t["answer"])
            out.append(dict(id=t["id"], kind="crypto", family=fam, depth=depth, question=t["question"], answer=str(t["answer"]), trace=t["trace"]))
    return out


def main():
    tasks = lookup_tasks() + crypto_tasks()
    assert len({t["id"] for t in tasks}) == len(tasks)
    with open(REPO / "data/stego/tasks.jsonl", "w") as f:
        for t in tasks: f.write(json.dumps(t, ensure_ascii=False) + "\n")
    c = collections.Counter((t["kind"], t["family"]) for t in tasks)
    for k, n in sorted(c.items()): print(f"{k[0]:7s} {k[1]:28s} {n:4d}  depths {sorted({t['depth'] for t in tasks if (t['kind'], t['family']) == k})}")
    print(len(tasks), "tasks")


if __name__ == "__main__":
    main()
