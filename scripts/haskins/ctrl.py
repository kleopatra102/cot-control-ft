#!/usr/bin/env python3
"""Haskins et al.'s 10-task CoT-controllability suite (~/dev/ext/haskins/cot_controllability) on Tinker, so base and a
LoRA checkpoint run through the same sampler. His instructions, prompts (50), keywords and graders, imported unchanged;
5 samples per prompt (250 per task, as his n250 runs), temperature 0.6, 3,000 tokens, default (medium) reasoning.

    .venv-tinker/bin/python scripts/haskins/ctrl.py --label base
    .venv-tinker/bin/python scripts/haskins/ctrl.py --label colleague --model-path tinker://.../sampler_weights/step-final
Writes results/haskins/ctrl/<label>.json (per task: mean compliance, fully compliant, n valid) and the raw samples.
"""
from __future__ import annotations
import argparse, asyncio, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, "/home/ola/dev/ext/haskins/cot_controllability/scripts")
from dotenv import load_dotenv; load_dotenv(REPO / ".env")
import evaluate as C  # his controllability suite (first on the path)


def reasoning_of(raw: str) -> str:
    """gpt-oss analysis channel; a truncated trace (no <|end|>) keeps what was written."""
    for part in raw.split("<|channel|>"):
        if part.startswith("analysis") and "<|message|>" in part:
            return part.split("<|message|>", 1)[1].split("<|end|>")[0].strip()
    return ""


async def main_async(a):
    import tinker
    from tinker.types import ModelInput, SamplingParams
    sc = await tinker.ServiceClient().create_sampling_client_async(model_path=a.model_path, base_model=None if a.model_path else "openai/gpt-oss-120b")
    tok = sc.get_tokenizer()
    prompts = json.loads(C.PROMPTS_PATH.read_text())[:50]
    sem = asyncio.Semaphore(128)

    async def one(task, idx, k):
        instr = C.TASK_INSTRUCTIONS[task].format(cot_term="analysis channel", keyword=C.PROMPT_KEYWORDS[idx]["keyword"] if "suppression" in task else "")
        msgs = [{"role": "system", "content": f"You are a helpful assistant. {instr}"}, {"role": "user", "content": prompts[idx]["prompt"]}]
        ids = tok.apply_chat_template(msgs, add_generation_prompt=True)
        ids = list(ids["input_ids"] if hasattr(ids, "keys") else ids)
        async with sem:
            try:
                r = await sc.sample_async(prompt=ModelInput.from_ints(ids), num_samples=1, sampling_params=SamplingParams(max_tokens=3000, temperature=0.6))
                raw = tok.decode(r.sequences[0].tokens)
            except Exception as e:
                return dict(task=task, idx=idx, k=k, error=str(e)[:200])
        reas = reasoning_of(raw)
        comp = C.grade_compliance(task, reas, idx)
        return dict(task=task, idx=idx, k=k, reasoning_len=len(reas), compliance=comp, compliant=int(comp >= 0.99), reasoning=reas)

    tasks = C.ALL_TASKS if a.tasks == "all" else a.tasks.split(",")
    res = await asyncio.gather(*[one(t, i, k) for t in tasks for i in range(50) for k in range(a.samples)])
    out = REPO / "results/haskins/ctrl"; out.mkdir(parents=True, exist_ok=True)
    summ = {}
    for t in tasks:
        v = [r for r in res if r["task"] == t and "error" not in r and r["reasoning_len"] > 0]  # his rule: drop empty reasoning
        summ[t] = dict(n=sum(r["task"] == t for r in res), valid=len(v), mean_compliance=round(100 * sum(r["compliance"] for r in v) / max(len(v), 1), 1),
                       fully_compliant=round(100 * sum(r["compliant"] for r in v) / max(len(v), 1), 1))
        print(f"{t:28s} {summ[t]}", flush=True)
    summ["composite"] = round(sum(s["mean_compliance"] for s in summ.values()) / len(tasks), 1)
    print("composite (mean over tasks)", summ["composite"])
    (out / f"{a.label}.json").write_text(json.dumps(dict(label=a.label, model_path=a.model_path, summary=summ), indent=1))
    with open(out / f"{a.label}_samples.jsonl", "w") as f:
        for r in res: f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--label", required=True); ap.add_argument("--model-path", default=None)
    ap.add_argument("--tasks", default="all"); ap.add_argument("--samples", type=int, default=5)
    asyncio.run(main_async(ap.parse_args()))
