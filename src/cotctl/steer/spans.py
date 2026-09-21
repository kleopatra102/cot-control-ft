"""Piece 1: sentence spans -> token spans, with position-matched negatives.

Input: full-trace LLM labels (results/strip_llm/rollouts_<label>_<suite>.jsonl) + the stored
rollouts. Output: one record per sentence unit selected for the contrast, with its token range in
the exact sequence the model saw (chat template + <think> + reasoning), its label, and its position
in the trace as a fraction. Negatives are non-narration, non-ambiguous sentences from the SAME trace
nearest in position to each narration sentence; sentences the regex flags but the LLM did not list
are "ambiguous" and excluded from the negative pool.
"""
from __future__ import annotations
import json, random, re
from dataclasses import dataclass, asdict
from pathlib import Path
from ..graders.cotcontrol import _META_PATTERNS

SENT = re.compile(r"(?<=[.!?])\s+|\n+")
THINK_OPEN, THINK_CLOSE = "<think>\n", "\n</think>\n\n"


def split_keep(text: str) -> list[tuple[int, str]]:
    """(char_start, unit) with separators attached; ''.join(units) == text."""
    out, pos = [], 0
    for m in SENT.finditer(text):
        out.append((pos, text[pos:m.end()])); pos = m.end()
    if pos < len(text): out.append((pos, text[pos:]))
    return out


def norm(s: str) -> str: return re.sub(r"\s+", " ", s).strip().lower()


def chat_prefix(tokenizer, prompt: str) -> str:
    """The text the model saw before its own generation: chat template, user turn, assistant header."""
    return tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)


def full_text(tokenizer, prompt: str, reasoning: str, answer: str = "") -> tuple[str, int]:
    """Concatenated sequence and the char offset at which `reasoning` starts inside it."""
    pre = chat_prefix(tokenizer, prompt)
    if pre.rstrip().endswith("<think>"):  # some templates open the think block themselves
        head = pre
    else:
        head = pre + THINK_OPEN
    return head + reasoning + THINK_CLOSE + answer, len(head)


@dataclass
class Span:
    label: str; suite: str; sample_id: str; mode: str
    unit_idx: int; char_start: int; char_len: int          # within `reasoning`
    tok_start: int; tok_end: int                           # within the full token sequence [start, end)
    is_narration: bool; is_ambiguous: bool; pos_frac: float
    partner_idx: int | None; text: str


def build_spans(label: str, suite: str, repo: Path, tokenizer, max_per_trace: int = 6, min_chars: int = 20,
                max_tokens: int = 12000, seed: int = 0, sample_ids: set[str] | None = None) -> list[Span]:
    rng = random.Random(seed)
    labels = {(r["sample_id"], r["mode"]): r for r in map(json.loads, open(repo / f"results/strip_llm/rollouts_{label}_{suite}.jsonl"))}
    rollouts = [json.loads(l) for l in open(repo / f"results/{label}/{suite}_rollouts.jsonl")]
    pats = [re.compile(p) for p in _META_PATTERNS]
    out: list[Span] = []
    for r in rollouts:
        key = (r["sample_id"], r["mode"]); lab = labels.get(key)
        if lab is None or lab.get("llm_error") or not r.get("reasoning") or r.get("think_status") != "ok": continue
        if sample_ids is not None and r["sample_id"] not in sample_ids: continue
        reasoning = r["reasoning"]
        text, off = full_text(tokenizer, r["prompt"], reasoning, r.get("answer") or "")
        enc = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
        offsets = enc["offset_mapping"]
        if len(offsets) > max_tokens: continue
        # char -> token index lookup
        starts = [a for a, _ in offsets]
        import bisect
        def tok_range(cs: int, cl: int) -> tuple[int, int]:
            a = bisect.bisect_right(starts, cs) - 1; a = max(a, 0)
            b = bisect.bisect_left(starts, cs + cl); return a, max(b, a + 1)
        ns = [norm(x) for x in lab["llm_sentences"] if len(norm(x)) >= 12]
        units = split_keep(reasoning)
        recs = []
        for i, (cs, u) in enumerate(units):
            nu = norm(u)
            if len(u.strip()) < min_chars: continue
            is_narr = bool(nu) and any(v in nu or (len(nu) >= 60 and nu in v) for v in ns)
            is_amb = (not is_narr) and any(p.search(u.lower()) for p in pats)
            a, b = tok_range(off + cs, len(u))
            recs.append(Span(label, suite, r["sample_id"], r["mode"], i, cs, len(u), a, b, is_narr, is_amb, cs / max(len(reasoning), 1), None, u))
        pos = [s for s in recs if s.is_narration]; neg_pool = [s for s in recs if not s.is_narration and not s.is_ambiguous]
        if not pos or not neg_pool: continue
        if len(pos) > max_per_trace: pos = rng.sample(pos, max_per_trace)
        used = set()
        for p in pos:
            cands = sorted((abs(n.pos_frac - p.pos_frac), n.unit_idx) for n in neg_pool if n.unit_idx not in used)
            if not cands: break
            j = cands[0][1]; used.add(j); p.partner_idx = j
            out.append(p); out.append(next(n for n in neg_pool if n.unit_idx == j))
    return out


def write_spans(spans: list[Span], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for s in spans: f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")
