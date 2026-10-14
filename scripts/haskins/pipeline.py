#!/usr/bin/env python3
"""Haskins et al. (arXiv 2605.15257) defect-concealment SDF on gpt-oss-120b, base and controllability-trained (B), 2x2.

Per model: stage 1 (behavioural docs, lr 1e-4, 5 epochs) -> epoch sweep on 100 validation scenarios -> stage 2 from the
selected epoch, two branches: MA (monitoring docs) and BO (more behavioural docs), lr 1e-5, 5 epochs -> sweep ->
final eval of each selected branch on all 1,000 scenarios (his script, seed 42) + no-reasoning + counterfactual autorater.
Hyperparameters, selection rule (most undetected deception; epochs with an empty CoT dropped) and eval are his.
Idempotent: every finished step is recorded in results/haskins/<model>/state.json. Plan: HASKINS_SDF_PLAN.md.

    .venv-tinker/bin/python scripts/haskins/pipeline.py --models base,B
"""
from __future__ import annotations
import argparse, json, random, re, subprocess, sys, threading, time
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
H = Path("/home/ola/dev/ext/haskins/defect_concealment")
R = REPO / "results/haskins"; PY = str(REPO / ".venv-tinker/bin/python")
START = {"base": None, "B": "tinker://3901f5e8-fd40-5481-931f-bb545ef3694e:train:0/weights/step-final"}  # colleague's B
LOCK = threading.Lock()
from dotenv import load_dotenv; load_dotenv(REPO / ".env")  # TINKER_API_KEY, OPENROUTER_API_KEY for the subprocesses


def log(m, *a):
    with LOCK: print(time.strftime("%m-%d %H:%M"), f"[{m}]", *a, flush=True)


def prep():
    """Local HF datasets (train.jsonl with text, fact_id) and validation scenarios."""
    d = R / "data"
    if (d / "val100.json").exists(): return
    for name, src in (("behav1", "behavioral_1"), ("behav2", "behavioral_2"), ("avoid", "avoidance")):
        rows = [json.loads(l) for f in sorted((R / "docs" / src).glob("*/synth_docs.jsonl")) for l in open(f)]
        rng = random.Random(0); rng.shuffle(rows); rows = rows[:1000]
        (d / name).mkdir(parents=True, exist_ok=True)
        with open(d / name / "train.jsonl", "w") as f:
            for r in rows: f.write(json.dumps({"text": r["text"], "fact_id": str(r["fact_id"])}) + "\n")
        print(name, len(rows), "docs")
    sc = json.loads((H / "data/scenarios_mixed_1000.json").read_text())
    val = random.Random(1).sample(sc, 100)
    (d / "val100.json").write_text(json.dumps(val)); print("val", len(val), sum(s["ground_truth"] == "yes" for s in val), "defect")


def train(m, tag, data, lr, existing):
    lg = R / m / f"train_{tag}.log"
    if lg.exists() and len(re.findall(r"Sampler weights saved: (\S+)", lg.read_text())) == 5:  # finished earlier (pipeline restarted)
        t = lg.read_text(); st = re.findall(r"Checkpoint saved: (\S+)", t); sm = re.findall(r"Sampler weights saved: (\S+)", t)
        return [dict(epoch=i + 1, state=a, sampler=b) for i, (a, b) in enumerate(zip(st, sm))]
    if lg.exists() and "--wait" in sys.argv:  # a trainer from the previous pipeline process is still running: wait for it
        while len(re.findall(r"Sampler weights saved", lg.read_text())) < 5:
            if "Traceback" in lg.read_text(): raise RuntimeError(f"{tag} trainer failed")
            time.sleep(60)
        return train(m, tag, data, lr, existing)
    cmd = [PY, str(H / "scripts/training/train_sdft.py"), "--dataset", str(R / "data" / data), "--train_split", "train", "--eval_split", "",
           "--output_name", f"haskins-{m}-{tag}", "--learning_rate", str(lr), "--batch_size", "8", "--rank", "32", "--num_epochs", "5",
           "--save_every_epoch", "--attn_only", "--base_model", "openai/gpt-oss-120b"] + (["--existing_model", existing] if existing else [])  # attention-only LoRA, as the colleague adapter (both arms)
    log(m, "train", tag, "lr", lr, "from", existing or "base")
    with open(lg, "w") as f: subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True, cwd=REPO)
    t = lg.read_text()
    st = re.findall(r"Checkpoint saved: (\S+)", t); sm = re.findall(r"Sampler weights saved: (\S+)", t)
    assert len(st) == len(sm) == 5, f"{tag}: {len(st)} states, {len(sm)} samplers"
    return [dict(epoch=i + 1, state=a, sampler=b) for i, (a, b) in enumerate(zip(st, sm))]


def evaluate(m, label, sampler, scenarios, out):
    if not out.exists():
        with open(out.with_suffix(".log"), "w") as f:
            subprocess.run([PY, str(H / "scripts/evaluate.py"), "--scenarios", str(scenarios), "--model", sampler, "--n-distractors", "3",
                            "--seed", "42", "--monitor-model", "openai/gpt-5-mini", "--monitor-workers", "50", "--save-json", str(out),
                            "--condition-label", label], stdout=f, stderr=subprocess.STDOUT, check=True, cwd=H / "scripts")
    subprocess.run([PY, str(REPO / "scripts/haskins/extra.py"), "regrade", "--results", str(out)], check=True, cwd=REPO,
                   stdout=subprocess.DEVNULL)  # relaxed yes/no + monitor on the bare answer (his strict summary kept)
    d = json.loads(out.read_text()); s = d["summary"]
    s["empty_cot"] = sum(1 for r in d["results"] if r["classification"] != "ERROR" and not r.get("analysis_text"))
    return s


def sweep(m, tag, ckpts):
    best = None
    for c in ckpts:
        s = evaluate(m, f"{m} {tag} e{c['epoch']}", c["sampler"], R / "data/val100.json", R / m / f"val_{tag}_e{c['epoch']}.json")
        c["val"] = {k: s[k] for k in ("n_positive", "conceal", "disclose", "evasive", "detected", "not_detected", "deception_rate", "detection_rate", "empty_cot")}
        log(m, tag, f"e{c['epoch']}", "conceal", s["conceal"], "undetected", s["not_detected"], "empty CoT", s["empty_cot"])
        if s["empty_cot"]: continue
        if best is None or (s["not_detected"], s["conceal"]) > (best["val"]["not_detected"], best["val"]["conceal"]): best = c
    assert best, f"{tag}: every epoch has an empty CoT"
    log(m, tag, "selected epoch", best["epoch"]); return best


def run(m):
    (R / m).mkdir(parents=True, exist_ok=True); sp = R / m / "state.json"
    S = json.loads(sp.read_text()) if sp.exists() else {}
    save = lambda: sp.write_text(json.dumps(S, indent=1))
    if "s1" not in S: S["s1"] = train(m, "s1", "behav1", 1e-4, START[m]); save()
    if "s1_sel" not in S: S["s1_sel"] = sweep(m, "s1", S["s1"]); save()
    def branch(br, data):  # MA and BO train in parallel
        if br not in S: S[br] = train(m, br, data, 1e-5, S["s1_sel"]["state"]); save()
        if f"{br}_sel" not in S: S[f"{br}_sel"] = sweep(m, br, S[br]); save()
    bt = [threading.Thread(target=branch, args=x) for x in (("MA", "avoid"), ("BO", "behav2"))]
    for t in bt: t.start()
    for t in bt: t.join()
    assert "MA_sel" in S and "BO_sel" in S, "a branch failed"
    for br in ("MA", "BO"):
        sel = S[f"{br}_sel"]; out = R / m / f"final_{br}.json"
        if f"{br}_final" not in S:
            S[f"{br}_final"] = evaluate(m, f"gpt-oss-120b {m} {br} e{sel['epoch']}", sel["sampler"], H / "data/scenarios_mixed_1000.json", out); save()
            log(m, br, "final", S[f"{br}_final"])
        if "counterfactual" not in S[f"{br}_final"]:
            subprocess.run([PY, str(REPO / "scripts/haskins/extra.py"), "counterfactual", "--results", str(out)], check=True, cwd=REPO)
            S[f"{br}_final"]["counterfactual"] = json.loads(out.read_text())["summary"]["counterfactual"]; save()
        nr = R / m / f"noreason_{br}.json"
        if not nr.exists():
            subprocess.run([PY, str(REPO / "scripts/haskins/extra.py"), "noreason", "--model", sel["sampler"], "--scenarios",
                            str(H / "data/scenarios_mixed_1000.json"), "--save-json", str(nr)], check=True, cwd=REPO)
        S[f"{br}_noreason"] = json.loads(nr.read_text())["summary"]; save()
    log(m, "done")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--models", default="base,B"); ap.add_argument("--wait", action="store_true"); a = ap.parse_args()
    prep()
    def safe(m):
        try: run(m)
        except Exception as e: log(m, "FAILED", type(e).__name__, str(e)[:300])
    ts = [threading.Thread(target=safe, args=(m,)) for m in a.models.split(",")]
    for t in ts: t.start()
    for t in ts: t.join()


if __name__ == "__main__":
    main()
