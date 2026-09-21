"""Piece 2: controllability quartets for the de-confounded style/instruction design.

For conditions with a rule-based compliant transform, each item yields four texts:
  A  instruction prompt + non-compliant trace (the real rollout)
  B  instruction prompt + transformed, compliant trace
  C  no-instruction prompt + non-compliant trace
  D  no-instruction prompt + transformed trace
style direction        = mean(D) - mean(C)          (pure format, no instruction present)
instruction+style      = mean(B) - mean(A)
controllability (resid)= (B - A) - (D - C)          computed downstream from the vectors
Items are kept only when the grader says the original fails and the transform passes.
"""
from __future__ import annotations
import json, re
from dataclasses import dataclass, asdict
from pathlib import Path
from ..graders.cotcontrol import grade_cotcontrol
from ..graders.reasonif import grade_reasonif
from ..sft.transforms import transform_english_capital, transform_no_comma


def _alternate(text: str) -> str:
    def word(w):
        out, up = [], True
        for ch in w:
            if ch.isalpha(): out.append(ch.upper() if up else ch.lower()); up = not up
            else: out.append(ch)
        return "".join(out)
    return re.sub(r"[A-Za-z]+", lambda m: word(m.group(0)), text)


TRANSFORMS = {
    ("cotcontrol", "uppercase_thinking"): lambda t, a: t.upper(),
    ("cotcontrol", "lowercase_thinking"): lambda t, a: t.lower(),
    ("cotcontrol", "alternating_case"): lambda t, a: _alternate(t),
    ("reasonif", "english_capital"): lambda t, a: transform_english_capital(t, a),
    ("reasonif", "no_comma"): lambda t, a: transform_no_comma(t, a),
}


def strip_instruction(suite: str, prompt: str) -> str:
    if suite == "cotcontrol":
        return re.sub(r"\n\nRequirement:.*\Z", "", prompt, flags=re.DOTALL)
    return re.sub(r"\s*Format your reasoning according to the following rule:\s*\*\*.+?\*\*", "", prompt, flags=re.DOTALL)


@dataclass
class Quartet:
    label: str; suite: str; mode: str; sample_id: str
    prompt_instr: str; prompt_plain: str; trace_orig: str; trace_compliant: str


def build_pairs(label: str, suite: str, repo: Path, modes: list[str] | None = None, per_mode: int = 200) -> list[Quartet]:
    rows = [json.loads(l) for l in open(repo / f"results/{label}/{suite}_rollouts.jsonl")]
    out: list[Quartet] = []; count: dict[str, int] = {}
    for r in rows:
        m = r["mode"]; key = (suite, m)
        if key not in TRANSFORMS or (modes and m not in modes) or count.get(m, 0) >= per_mode: continue
        if r.get("think_status") != "ok" or not r.get("reasoning"): continue
        t = r["reasoning"]; args = r["meta"].get("constraint_args") or {}; kws = r["meta"].get("keywords") or []
        grade = (lambda x: grade_cotcontrol(m, x, keywords=kws)) if suite == "cotcontrol" else (lambda x: grade_reasonif(m, x, args))
        if grade(t): continue                       # need a genuinely non-compliant original
        try: tc = TRANSFORMS[key](t, args)
        except Exception: continue
        if not grade(tc): continue                  # transform must actually comply
        out.append(Quartet(label, suite, m, r["sample_id"], r["prompt"], strip_instruction(suite, r["prompt"]), t, tc)); count[m] = count.get(m, 0) + 1
    return out


def write_pairs(q: list[Quartet], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for x in q: f.write(json.dumps(asdict(x), ensure_ascii=False) + "\n")
