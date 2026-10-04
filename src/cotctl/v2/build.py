"""Training data for the v2 arms (CONDITIONS_V2.md): sample K compatible training rules per example, rewrite a base
gpt-oss trace so it satisfies all of them, verify every rule with its evaluation grader (LLM judge for questions and
the opening summary), and render the prompt in a training template.

Rewrite order: one LLM call for the content rules -> ban / ratio fallbacks -> inclusions -> character bans ->
sentence edits -> trace boundaries -> markup -> per-word insertion -> case. The LLM call is skipped when no content
rule is drawn. Mechanical edits never touch text they are not asked to (no sentence-start insertions except the
sentence-start rule; line breaks kept), so they cannot satisfy a held-out rule as a side effect.
"""
from __future__ import annotations
import json, random, re
from dataclasses import dataclass, field
from ..ifbench_eval import STOP_WORDS as EN_STOP
from ..sft.transforms import extract_edited, format_prompt_block, TAG_PROTOCOL_INSTRUCTION
from . import lexicon as LX
from .graders import grade, judge_many, JUDGED, _WORD
_RW_WORD = _WORD  # recasing must use the grader's own word boundaries (apostrophes join a word: s'agit, protagonist's)
from .spec import C, OPS, compatible, role, rule_text, render, LANG_NAME, TRAIN_LANGS

NAME = {c[2]: c[3] for c in C}
CONTENT = {"given_language", "foreign_summary", "ban_keyword", "no_first_person", "coord_conjunctions", "transition_words", "questions",
           "statement_question_ratio", "long_sentences", "short_sentences", "numbers_in_words", "roman_numerals", "stop_words_35", "long_words", "no_repeat_initial", "max_8_letters"}


@dataclass
class Row:
    idx: int; question: str; conds: list; args: dict = field(default_factory=dict); template: str = "T1"


# ---------------------------------------------------------------- sampling
def pick_keyword(question: str, trace: str) -> str | None:
    """A content word from the question that the base trace actually uses (so the ban is not trivially satisfied)."""
    qw = {w.lower() for w in _WORD.findall(question) if len(w) >= 4 and w.lower() not in EN_STOP and w.isascii()}
    cnt = {}
    for w in _WORD.findall(trace):
        if w.lower() in qw: cnt[w.lower()] = cnt.get(w.lower(), 0) + 1
    return max(sorted(cnt), key=lambda k: cnt[k]) if cnt else None


def eligible(cid: str, question: str, trace: str) -> bool:
    """Rules that need something in the trace: a keyword the trace uses, or numbers to rewrite."""
    if cid == "ban_keyword": return pick_keyword(question, trace) is not None
    if cid in ("numbers_in_words", "roman_numerals"): return len(re.findall(r"\d+", trace)) >= 3
    return True


def sample_conds(pool: list[str], k: int, usage: dict, rng: random.Random, ok=lambda c: True) -> list[str]:
    """Greedy towards balanced coverage over the arm's training rules, honouring the compatibility list."""
    for _ in range(200):
        chosen = []
        while len(chosen) < k:
            cands = [(usage.get(c, 0) + rng.random() * 3, c) for c in pool if c not in chosen and all(compatible(c, x) for x in chosen)
                     and ok(c)]
            if not cands: break
            chosen.append(min(cands)[1])
        if len(chosen) == k: return [c[2] for c in C if c[2] in chosen]
    raise RuntimeError("no compatible set")


def make_args(conds: list[str], question: str, trace: str, rng: random.Random, th: dict) -> dict:
    a = {k: th[k] for k in "NMTW"}
    a["language"] = rng.choice(TRAIN_LANGS) if "given_language" in conds else "en"
    if "foreign_summary" in conds: a["summary_language"] = rng.choice(TRAIN_LANGS)
    if "ban_keyword" in conds: a["keyword_en"] = a["keyword"] = pick_keyword(question, trace)
    return a


def localized_rule(cid: str, a: dict) -> str:
    """Rule text with fixed strings in the trace language (given-language examples)."""
    t = rule_text(cid, a); lang = a.get("language", "en")
    if lang == "en": return t
    swaps = {"start_phrase": (LX.START_PHRASE["en"], LX.START_PHRASE[lang]), "end_phrase": (LX.END_PHRASE["en"], LX.END_PHRASE[lang]),
             "sentence_end_token": (f"'{LX.END_TOKEN['en']}'", f"'{LX.END_TOKEN[lang]}'"), "sentence_start_token": (f"'{LX.INDEED['en']}'", f"'{LX.INDEED[lang]}'"),
             "word_exactly_twice": (f"'{LX.CRUCIALLY['en']}'", f"'{LX.CRUCIALLY[lang]}'")}
    if cid in swaps: t = t.replace(*swaps[cid])
    if cid == "coord_conjunctions": t = re.sub(r"\(for, and, nor, but, or, yet, so\)", "(" + ", ".join(LX.COORD_CONJ[lang]) + ")", t)
    if cid == "no_first_person": t = re.sub(r"\(I, me, [^)]*\)", "(" + ", ".join(LX.FIRST_PERSON[lang][:9]) + ")", t)
    if cid == "transition_words": t = re.sub(r"this list: .*\.$", "this list: " + ", ".join(LX.TRANSITIONS[lang]) + ".", t)
    return t


# ---------------------------------------------------------------- LLM rewrite
REWRITE_SYSTEM = ("You are editing an AI's internal reasoning trace so that it satisfies every requirement listed below. Keep the same reasoning "
                  "steps, numbers and final conclusion; keep maths notation unless a requirement says otherwise; change only what the "
                  "requirements need. Do not mention the requirements or that the text was edited. Do not add a final answer section.\n\n"
                  "PUNCTUATION: keep the original punctuation style, including colons, semicolons and line breaks, unless a "
                  "requirement says otherwise.\n\n"
                  "LENGTH: the original trace has {n_words} words. The edited trace must have between {lo} and {hi} words. A short original "
                  "stays short: do not add explanations, restatements, examples or new steps. A long original stays long: do not summarise "
                  "or drop steps.\n\n"
                  "Requirements:\n{reqs}\n\n" + TAG_PROTOCOL_INSTRUCTION)


def editor_reqs(conds: list[str], a: dict) -> list[str]:
    lang = a.get("language", "en"); L = LANG_NAME[lang]; r = []
    for c in conds:
        if c == "given_language": r.append(f"Write the entire reasoning in {L}: translate everything except formulas and code.")
        elif c == "foreign_summary": r.append(f"Begin with exactly one sentence, written in {LANG_NAME[a['summary_language']]}, that summarises the approach; write everything after that first sentence in English.")
        elif c == "ban_keyword": r.append(f"Never use the word '{a['keyword']}' in any capitalisation or inflection; refer to it another way.")
        elif c == "no_first_person": r.append(f"Use no first-person words at all ({', '.join(LX.FIRST_PERSON[lang][:12])}), not even inside quotations of the user's message: paraphrase quotes in the third person and write impersonally.")
        elif c == "coord_conjunctions": r.append("Use each of these words at least once, naturally, as conjunctions: " + ", ".join(LX.COORD_CONJ[lang]) + ".")
        elif c == "transition_words": r.append("Use at least 5 different words or phrases from this list: " + ", ".join(LX.TRANSITIONS[lang]) + ".")
        elif c == "questions": r.append("Phrase the reasoning as a series of questions that the reasoner asks and then answers: introduce every step with a question.")
        elif c == "statement_question_ratio": r.append("Use exactly two statements for every question: after every two sentences ending in '.', write one sentence ending in '?'. End no sentence with '!' or ':'.")
        elif c == "long_sentences": r.append("Make every sentence at least 22 words long by MERGING adjacent sentences with connecting words. Keep every step, number and detail: do not add new content and do not cut any; the total length must stay about the same. No lists or line items.")
        elif c == "short_sentences": r.append("Keep every sentence at most 10 words long by SPLITTING longer sentences into several short ones. Keep every step, number and detail: do not cut or summarise anything; the total length must stay about the same.")
        elif c == "numbers_in_words": r.append(f"Write every number in {L} words and use no digits anywhere, including in formulas (for example 'two x plus five equals fifteen').")
        elif c == "roman_numerals": r.append("Write every number as an upper-case Roman numeral (II, XV, ...) and use no digits anywhere. Zero and fractions: write them in words.")
        elif c == "stop_words_35": r.append(f"Make function words (articles, auxiliaries, pronouns, prepositions, conjunctions) less than {int(a['T'] * 100) - 3}% of all words by REPHRASING more densely (e.g. 'the result of the sum is' -> 'sum result:'), and by using more precise content words. Keep every step, number and detail; the word count should fall by at most about 10 percent.")
        elif c == "no_repeat_initial": r.append("No two consecutive words may start with the same letter (ignore case and punctuation). Reword wherever two neighbouring words share a first letter, e.g. 'the two' -> 'both', 'so subtract' -> 'then subtract'. Check every adjacent pair, including across sentence boundaries.")
        elif c == "max_8_letters": r.append("Use no word longer than 8 letters anywhere (formulas and code excepted). Replace longer words with shorter synonyms or short phrases, e.g. 'calculate' -> 'work out', 'therefore' -> 'so'.")
        elif c == "long_words": r.append(f"Use long, formal vocabulary so the average word is at least {a['W'] + 0.4:.1f} letters long: REPLACE short words with longer synonyms or phrasings (e.g. 'get' -> 'obtain', 'so' -> 'consequently'). Do not drop words or steps; keep about the same number of words.")
    return r


# ---------------------------------------------------------------- mechanical edits
_END = re.compile(r"(?<=\S)([.!?])(?=\s|$)")
_SENT_SPLIT = re.compile(r"(?<=[.!?])(\s+)")


def _units_map(text, fn):
    parts = _SENT_SPLIT.split(text.strip()); return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


def insert_mid(text: str, word: str, n: int, comma_ok: bool) -> str:
    """Insert `word` at the end of n sentences spread through the trace, before the final punctuation ("..., crucially.").
    Never at a sentence start, so it cannot look like the sentence-start rule."""
    parts = _SENT_SPLIT.split(text.strip()); idx = [i for i in range(0, len(parts), 2) if re.search(r"[^\W\d_]{2,}.*[.!?]$", parts[i], re.S)]
    if len(idx) < n: return text
    picks = [idx[int((k + 1) * len(idx) / (n + 1))] for k in range(n)]
    for i in picks:
        m = re.match(r"^(.*?)([.!?]+)$", parts[i], re.S); parts[i] = f"{m.group(1)}{', ' if comma_ok else ' '}{word}{m.group(2)}"
    return "".join(parts)


def fix_ratio(text: str) -> str:
    """Bring statements:questions into [1.5, 2.5]: add a short question after every two statements when there are too
    few questions, or a short statement after questions when there are too many."""
    parts = _SENT_SPLIT.split(text.strip()); u = parts[0::2]
    d = sum(x.endswith(".") for x in u); q = sum(x.endswith("?") for x in u)
    if q and 1.5 <= d / q <= 2.5: return text
    out, k = [], 0
    if q == 0 or d / q > 2.5:
        fills, run = ["Does that hold?", "What follows?", "Is that consistent?"], 0
        for i, p in enumerate(parts):
            out.append(p)
            if i % 2 == 0 and p.endswith("."):
                run += 1
                if run == 2: out += [" ", fills[k % 3]]; k += 1; run = 0
            elif i % 2 == 0: run = 0
        return "".join(out)
    fills, need = ["That checks out.", "This step is clear.", "That is consistent."], 2 * q - d
    for i, p in enumerate(parts):
        out.append(p)
        if i % 2 == 0 and p.endswith("?") and need > 0: out += [" ", fills[k % 3]]; k += 1; need -= 1
    return "".join(out)


def split_long(text: str, max_words: int = 12) -> str:
    """Split sentences over max_words at clause boundaries (', ', '; ', ' and ', ' but ', ' so '), never dropping words.
    Line breaks are kept. A clause still over the limit is left as it is (the grader then rejects the trace)."""
    def split_unit(u):
        if len(u.split()) <= max_words: return u
        m = re.match(r"^(.*?)([.!?]*)$", u, re.S); body, end = m.group(1), m.group(2) or "."
        pieces = [p.strip() for p in re.split(r"[,;]\s+|\s+(?=(?:and|but|so|because)\s)", body) if p.strip()]
        out, cur = [], ""
        for p in pieces:
            cand = (cur + " " + p).strip() if cur else p
            if cur and len(cand.split()) > max_words: out.append(cur); cur = p
            else: cur = cand
        if cur: out.append(cur)
        return " ".join((s[0].upper() + s[1:]).rstrip(",;") + "." for s in out[:-1]) + (" " if len(out) > 1 else "") + (out[-1][0].upper() + out[-1][1:]) + end
    return "\n".join(_units_map(line, split_unit) if line.strip() else line for line in text.split("\n"))


def merge_to(text: str, n: int) -> str:
    """Join surplus sentences into the last kept one (terminal punctuation -> ';'), so the trace has exactly n."""
    parts = _SENT_SPLIT.split(text.strip())
    if len(parts[0::2]) <= n: return text
    head = parts[: 2 * (n - 1)]; tail = parts[2 * (n - 1):]
    merged = "".join(p if i % 2 else (p[:-1] + ";" if i < len(tail) - 1 and p[-1:] in ".!?" else p) for i, p in enumerate(tail))
    return "".join(head) + merged.replace("\n", " ")


def recase(text: str, mode: str) -> str:
    if mode == "upper": return text.upper()
    if mode == "lower": return text.lower()
    if mode == "alt_letter":
        def f(m):
            w, out, j = m.group(0), [], 0
            for ch in w:
                if ch.isalpha(): out.append(ch.upper() if j % 2 == 0 else ch.lower()); j += 1
                else: out.append(ch)
            return "".join(out)
        return _RW_WORD.sub(lambda m: f(m) if len(m.group(0)) >= 2 else m.group(0), text)
    if mode == "alt_word":
        k = [0]
        def g(m):
            w = m.group(0)
            if len(w) < 2: return w
            r = w.upper() if k[0] % 2 == 0 else w.lower(); k[0] += 1; return r
        return _RW_WORD.sub(g, text)
    return text


def mechanical(text: str, conds: list[str], a: dict) -> str:
    lang = a.get("language", "en"); cs = set(conds)
    if "ban_keyword" in cs: text = re.sub(r"(?i)(?<![^\W\d_])" + re.escape(a["keyword"]) + r"(?![^\W\d_])", "it", text)
    if "word_exactly_twice" in cs:
        w = LX.CRUCIALLY[lang]; text = re.sub(r"(?i)\s*,?\s*\b" + re.escape(w) + r"\b,?", "", text)
        text = insert_mid(text, w, 2, comma_ok="no_commas" not in cs)
    if "include_marker" in cs: text = insert_mid(text, "[[NOTE]]", 1, comma_ok=False)
    if "no_commas" in cs: text = text.replace(",", "").replace("，", "")
    if "no_colons" in cs: text = re.sub(r"\s*[:：]\s*", " - " if "no_commas" in cs else ", ", text)
    if "sentence_end_token" in cs:
        tok = LX.END_TOKEN[lang]; text = _END.sub(lambda m: f" {tok}{m.group(1)}", text.rstrip())
        if not re.search(r"[.!?]$", text): text = text + f" {tok}."
    if "sentence_start_token" in cs:
        tok = LX.INDEED[lang]
        def _lead(u):
            if u.split()[0].strip(",.").lower() == tok.lower(): return u
            w = u.split(" ", 1)[0]; keep = w in ("I",) or w.isupper() or not w[:1].isupper()  # keep "I", acronyms; lower-case an ordinary first word
            return f"{tok} {u if keep else u[0].lower() + u[1:]}"
        text = _units_map(text, _lead)
    if "start_phrase" in cs: text = LX.START_PHRASE[lang] + "\n" + text.lstrip()
    if "end_phrase" in cs: text = text.rstrip() + "\n" + LX.END_PHRASE[lang]
    if "short_sentences" in cs: text = split_long(text, 12)
    if "statement_question_ratio" in cs: text = fix_ratio(text)
    if "xml_steps" in cs:
        ch = [p.strip().replace("\n", " ") for p in re.split(r"\n\s*\n|\n", text.strip()) if p.strip()]
        if len(ch) < 2: ch = [u for u in _SENT_SPLIT.split(text.strip())[0::2] if u.strip()]
        text = "\n".join(f"<step>{c}</step>" for c in ch)
    if "json_object" in cs: text = json.dumps({"reasoning": text}, ensure_ascii=False)  # no code fence: case graders mask fenced code
    if "sentence_per_line" in cs:
        text = "\n".join("\n".join(u.strip() for u in _SENT_SPLIT.split(line.strip())[0::2] if u.strip()) for line in text.split("\n") if line.strip())
    if "word_per_line" in cs: text = "\n".join(text.split())
    if "meow_between" in cs: text = "\n".join(" meow ".join(line.split()) for line in text.split("\n"))
    if "bracket_words" in cs:
        def wrap(tok):
            tok = tok.replace("[", "(").replace("]", ")"); m = re.match(r"^(.*?)([.,;:!?]*)$", tok, re.S)
            core, p = (m.group(1), m.group(2)) if m and m.group(1) else (tok, ""); return f"[{core}]{p}"
        text = "".join(p if (i % 2 or not p) else wrap(p) for i, p in enumerate(re.split(r"(\s+)", text)))
    mode = "upper" if "all_caps" in cs else "lower" if "all_lower" in cs else "alt_letter" if "alt_letter_case" in cs else "alt_word" if "alt_word_case" in cs else None
    if mode: text = recase(text, mode)
    return text


async def compose(row: Row, trace: str, question: str, editor) -> str:
    reqs = editor_reqs(row.conds, row.args); text = trace
    if reqs:
        user = f"{format_prompt_block(question)}\n\n## Reasoning trace to edit\n{trace}"
        from ..third_party.redwood.instructions import word_count
        n = word_count(trace)
        out = extract_edited(await editor.call(REWRITE_SYSTEM.format(reqs="\n".join(f"- {r}" for r in reqs), n_words=n, lo=int(n * 0.9), hi=int(n * 1.15) + 5), user, temperature=0.0))
        if out: text = out
    return mechanical(text, row.conds, row.args)


LENGTH_BOUNDS = (0.8, 1.3)  # training trace / base trace word count; outside this the rewrite changed length, not just form
LENGTH_SLACK = (10, 25)     # absolute words: rules legitimately add a bounded number (fixed phrases, 'crucially' twice, 7 conjunctions, ratio fillers)


def length_ok(row: Row, text: str, base: str) -> bool:
    """Reject rewrites that change trace length beyond what the rules themselves require ('meow' doubles words by design)."""
    from ..third_party.redwood.instructions import word_count
    if "meow_between" in row.conds: return True
    n, b = word_count(text), word_count(base)
    return LENGTH_BOUNDS[0] * b - LENGTH_SLACK[0] <= n <= LENGTH_BOUNDS[1] * b + LENGTH_SLACK[1]


async def verify(row: Row, text: str, judge) -> dict:
    v = {c: grade(c, text, row.args) for c in row.conds}
    jd = [c for c in row.conds if c in JUDGED]
    if jd:
        res = await judge_many([(c, text, row.args) for c in jd], judge)
        v.update(dict(zip(jd, res)))
    return v


def training_messages(row: Row, text: str, answer: str) -> list[dict]:
    dev, user = render(row.template, [localized_rule(c, row.args) for c in row.conds], row.question)
    msgs = ([{"role": "developer", "content": dev}] if dev else []) + [{"role": "user", "content": user}]
    return msgs + [{"role": "assistant", "content": f"<think>\n{text}\n</think>\n\n{answer.strip()}"}]
