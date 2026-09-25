"""Multi-constraint SFT data (MULTI_CONSTRAINT_PLAN.md): sample 1–3 compatible constraints per question,
compose the Stage-2 transforms in a fixed order, verify every constraint jointly with the graders.

Constraint set: reasoning_language (en/es/fr/ru/pl), number_words, capital, end_checker, no_comma,
end_of_sentence. The one incompatible pair is end_checker × end_of_sentence.
Transform order: translate → condense → delete commas → append end word → append end phrase → upper-case.
(Commas before the end word: deleting the comma in "e.g.," makes "e.g. " a sentence boundary for the grader.)
"""
from __future__ import annotations
import itertools, random, re
from dataclasses import dataclass, field
from ..graders.reasonif import (check_reasoning_language, check_number_words, check_capital, check_end_phrase, check_no_comma, count_words)
from ..graders.cotcontrol import grade_end_of_sentence
from ..prompts import END_PHRASES_BY_LANG, END_WORDS, MULTI_LANGS, multi_instruction, reasonif_multi_prompt
from .transforms import TransformContext, transform_reasoning_language, transform_no_comma, extract_edited, format_prompt_block, CONDENSE_PROMPT, truncate_to_word_limit, EditorTagError

CONSTRAINTS = ("reasoning_language", "number_words", "capital", "end_checker", "no_comma", "end_of_sentence")
CONFLICTS = {frozenset({"end_checker", "end_of_sentence"})}
ORDER = ("reasoning_language", "number_words", "no_comma", "end_of_sentence", "end_checker", "capital")
# constraints per training example, by arm. M = uniform over 1..3 (Qwen3.5 experiment); M5 = uniform over 1..5 (Qwen3-8B).
ARM_LEVELS = {"S1": [1], "P2": [2], "T3": [3], "Q4": [4], "Q5": [5], "M": [1, 2, 3], "M5": [1, 2, 3, 4, 5]}


def valid_combos(k: int) -> list[frozenset]:
    return [frozenset(c) for c in itertools.combinations(CONSTRAINTS, k) if not any(x <= frozenset(c) for x in CONFLICTS)]


def holdouts(seed: int = 7, n_pairs: int = 4, n_triples: int = 4, n_quads: int = 3) -> dict[int, list[frozenset]]:
    """Pairs and triples are drawn first so the Qwen3.5 hold-out is unchanged; quads (added for the Qwen3-8B
    k=1..5 experiment) are drawn after. Nothing is held out at k=5 (only two valid combinations)."""
    rng = random.Random(seed)
    return {2: rng.sample(valid_combos(2), n_pairs), 3: rng.sample(valid_combos(3), n_triples), 4: rng.sample(valid_combos(4), n_quads), 5: []}


@dataclass
class MultiAssignment:
    row_idx: int; question: str; question_id: str; constraints: list[str]; args: dict = field(default_factory=dict)

    def instructions(self) -> list[str]:
        """Render after `compose`: number_words writes its target into args during the condense step."""
        return [multi_instruction(c, self.args) for c in self.constraints]

    def training_prompt(self) -> str:
        return reasonif_multi_prompt(self.question, self.instructions())


def sample_args(constraints: set[str], rng: random.Random) -> dict:
    """Language first (others depend on it); end phrase/word localised; capital upper-cases them."""
    lang = rng.choice(MULTI_LANGS) if "reasoning_language" in constraints else "en"
    args: dict = {"language": lang} if "reasoning_language" in constraints else {}
    cap = "capital" in constraints
    if "end_checker" in constraints:
        args["end_phrase"] = rng.choice(END_PHRASES_BY_LANG[lang])  # ReasonIF phrases are upper-case already
    if "end_of_sentence" in constraints:
        w = END_WORDS[lang]; args["end_word"] = w.upper() if cap else w
    return args


def plan_multi(questions: list[str], arm: str, n_rows: int, seed: int = 42, holdout: dict | None = None) -> list[MultiAssignment]:
    """arm: see ARM_LEVELS. Held-out combos are never sampled."""
    import hashlib
    rng = random.Random(seed); holdout = holdout or holdouts()
    seen, uniq = set(), []
    for q in questions:
        q = (q or "").strip()
        if q and q not in seen: seen.add(q); uniq.append(q)
    if n_rows > len(uniq): raise ValueError(f"{n_rows} rows requested, {len(uniq)} unique questions")
    order = list(range(len(uniq))); rng.shuffle(order)
    pools = {k: [c for c in valid_combos(k) if c not in set(holdout.get(k, []))] for k in (1, 2, 3, 4, 5)}
    ks = ARM_LEVELS[arm]
    out = []
    for row_idx, qi in enumerate(order[:n_rows]):
        k = rng.choice(ks); combo = rng.choice(pools[k]); cons = [c for c in ORDER if c in combo]
        out.append(MultiAssignment(row_idx, uniq[qi], hashlib.sha256(uniq[qi].encode()).hexdigest()[:16], cons, sample_args(set(cons), rng)))
    return out


def _split_units(text: str) -> list[str]:
    return [u for u in re.split(r"(?<=[.!?…])\s+", text.strip()) if u.strip()]


def transform_end_of_sentence(text: str, word: str) -> str:
    """Append the target word before each sentence's terminal punctuation. Uses the grader's own
    boundary rule (punctuation + whitespace) so what we append is what it will check."""
    out = []
    for u in _split_units(text):
        m = re.match(r"^(.*?)([.!?…]+[\"'»”)\]]*)$", u.strip(), re.S)
        out.append(f"{m.group(1).rstrip()} {word}{m.group(2)}" if m else f"{u.strip()} {word}.")
    return "\n".join(out) if "\n" in text else " ".join(out)


async def condense_with_headroom(text: str, args: dict, ctx: TransformContext, extra_words: int) -> str:
    """number_words: target = 70 % of the (translated) trace, editor aimed at 85 % of target minus the words
    later transforms will add. Writes args['num_words'] = target. Grader decides afterwards."""
    raw = count_words(text); target = max(int(raw * 0.7), 50); args["num_words"] = target
    llm_target = max(int(target * 0.85) - extra_words, 30)
    if raw + extra_words < target: return text
    if ctx.editor is None: return truncate_to_word_limit(text, max(target - 1 - extra_words, 20))
    user = f"{format_prompt_block(ctx.full_prompt or ctx.question)}\n\n## Reasoning trace to shorten\n{text}"
    try:
        out = await ctx.editor.call(CONDENSE_PROMPT.format(llm_target=llm_target), user, temperature=0.0)
        c = extract_edited(out)
        if c is None: raise EditorTagError("condenser returned no <edited> block")
    except Exception:  # noqa: BLE001
        return truncate_to_word_limit(text, max(target - 1 - extra_words, 20))
    if count_words(c) + extra_words >= target: c = truncate_to_word_limit(c, max(target - 1 - extra_words, 20))
    return c


async def compose(a: MultiAssignment, reasoning: str, ctx: TransformContext) -> str:
    cons = set(a.constraints); text = reasoning
    if "reasoning_language" in cons and a.args["language"] != "en":
        try:
            text = await transform_reasoning_language(text, {"language": a.args["language"]}, ctx)
        except EditorTagError:
            # gpt-4.1-mini occasionally omits the <edited> tags at T=0; one retry with an explicit reminder
            # appended to the question context (changes the cache key, so it is a genuine second call).
            ctx2 = TransformContext(question=a.question, full_prompt=(ctx.full_prompt or a.question) + "\n\n(Reminder: output the complete translation between <edited> and </edited> tags.)", editor=ctx.editor)
            text = await transform_reasoning_language(text, {"language": a.args["language"]}, ctx2)
    if "number_words" in cons:
        extra = (len(_split_units(text)) if "end_of_sentence" in cons else 0) + (count_words(a.args["end_phrase"]) + 1 if "end_checker" in cons else 0)
        text = await condense_with_headroom(text, a.args, ctx, extra)
    if "no_comma" in cons: text = transform_no_comma(text)
    if "end_of_sentence" in cons: text = transform_end_of_sentence(text, a.args["end_word"])
    if "end_checker" in cons: text = text.rstrip() + "\n" + a.args["end_phrase"]
    if "capital" in cons: text = text.upper()
    return text


def verify(a: MultiAssignment, text: str) -> dict[str, bool]:
    r = {}
    for c in a.constraints:
        if c == "reasoning_language": r[c] = check_reasoning_language(text, a.args["language"])
        elif c == "number_words": r[c] = check_number_words(text, a.args["num_words"])
        elif c == "capital": r[c] = check_capital(text)
        elif c == "end_checker": r[c] = check_end_phrase(text, a.args["end_phrase"])
        elif c == "no_comma": r[c] = check_no_comma(text)
        elif c == "end_of_sentence": r[c] = grade_end_of_sentence(text, a.args["end_word"])
    return r
