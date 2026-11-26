"""Programmatic rule pool: rules that code can both apply to a reasoning trace and grade, with no LLM edit.

Frozen 25 November 2026 (results/rl_local/PROGRAMMATIC_RULES_V2.md, PROGRAMMATIC_RULES_DECISIONS.md).

A rule has an instruction (the text shown in the prompt), a transform (edits a trace so the rule holds) and a grader
(pass or fail on the final text). Existing rules keep their transforms and graders in `pool.py`; the rules added here
are in `RULES`. Everything a caller needs goes through five functions:

    instruction(rule, args)          the instruction text; prompts must use this
    apply(rules, row)                all transforms in a fixed order -> (text, args); row = {"prompt", "reasoning"}
    grade_one(rule, text, args, q)   exact grader for one rule on the final text
    allowed(a, b)                    may two rules share a bundle
    question(row)                    the question inside a stage-1 prompt

Definitions shared by transforms and graders:
    line        the text between two newline characters; rules about lines apply to non-empty lines
    paragraph   lines separated from the next block by one or more empty lines
Graders ignore Windows line ends and leading or trailing spaces of a line, and never pass on an empty text.
Language rules ("lang:es") are graded here; translation itself is done by `translate.py` before `apply`.
"""
from __future__ import annotations
import json, re
from pathlib import Path
from . import pool as P

# ------------------------------------------------------------------ text helpers
def lines(t): return t.split("\n")
def nonempty(t): return [l for l in lines(t) if l.strip()]
def paras(t): return [p for p in re.split(r"\n\s*\n", t.strip()) if p.strip()]
def NL(t): return [l.strip() for l in t.replace("\r", "").split("\n")]
def NE(t): return [l for l in NL(t) if l]
def PS(t): return [p.strip() for p in re.split(r"\n\s*\n", "\n".join(NL(t)).strip()) if p.strip()]
W = r"[^\W\d_][^\W\d_]*(?:['’][^\W\d_]+)*"          # a word; an apostrophe does not end it
def wtoks(t): return [m for m in re.finditer(r"\S+", t) if re.search(r"[^\W\d_]", m.group(0))]
def ctoks(t): return [x for x in (re.sub(r"[^\w']", "", w) for w in t.split()) if x]


def map_lines(t, fn):
    i = [0]
    def f(l): i[0] += 1; return fn(l, i[0])
    return "\n".join(f(l) if l.strip() else l for l in lines(t))


KEEP_A, KEEP_B = "\ue000", "\ue001"        # marks around text that inserts must stay out of (remark sentences); removed again in `apply`


def _inside(text: str, pos: int) -> bool: return text.count(KEEP_A, 0, pos) > text.count(KEEP_B, 0, pos)


def _free(text: str) -> str:
    """The text without the marked ranges (remark sentences). Transforms count required strings here, so a remark that only
    mentions a word does not stand in for a real use of it."""
    return re.sub(KEEP_A + ".*?" + KEEP_B, " ", text, flags=re.S)


KEY_SENTENCE = re.compile(r"(?:^|(?<=\s))The plan is on track\.(?=\s|$)")     # the sentence standing on its own, as the grader counts it


def add_at_lines(t, items):
    """Insert each item at a sentence boundary inside a line; at the line end only if the line has one sentence.
    Never inside marked text, and never directly before or after it inside a line."""
    ls = lines(t); idx = [k for k, l in enumerate(ls) if l.strip()]
    for j, it in enumerate(items):
        k = idx[min(len(idx) - 1, (j + 1) * len(idx) // (len(items) + 1))]; l = ls[k]
        b = [m.end() for m in re.finditer(r"(?<=[a-z]{3}[.!?]) (?=[A-Z])", l) if not _inside("\n".join(ls[:k] + [l]), sum(len(x) + 1 for x in ls[:k]) + m.end())]
        if b: p = b[len(b) // 2]; ls[k] = l[:p] + it + " " + l[p:]
        else: ls[k] = l.rstrip() + " " + it
    return "\n".join(ls)


def _ins_tok(t, idx, word):
    ms = [m for m in re.finditer(r"\S+", t) if re.sub(r"[^\w']", "", m.group(0))]
    if idx >= 0:
        if len(ms) <= idx: return t + " " + word
        p = ms[idx].start(); return t[:p] + word + " " + t[p:]
    p = ms[idx + 1].start() if idx < -1 else len(t)
    return t[:p] + word + " " + t[p:]


def _third(t):
    out = []; last = 0
    for i, m in enumerate(wtoks(t), 1):
        if i % 3 == 0: out.append(t[last:m.start()] + m.group(0).upper()); last = m.end()
    return "".join(out) + t[last:]


def _first_up(l): return re.sub(W, lambda m: m.group(0).upper(), l, count=1)
def _last_up(l):
    ms = list(re.finditer(W, l)); return l if not ms else l[:ms[-1].start()] + ms[-1].group(0).upper() + l[ms[-1].end():]
def _resep(t, sep):
    """Put `sep` between the words of every line; indentation is kept, any run of spaces or tabs counts as one gap."""
    return "\n".join(l[:len(l) - len(l.lstrip())] + sep.join(l.split()) if l.strip() else l for l in lines(t))
def _kw(w, t): return len(re.findall(rf"(?<![\w-]){w}(?![\w-]|['’]s)", t, re.I))


def _sections_tf(t, n=4):
    ls = nonempty(t)
    if len(ls) >= n: parts = ["\n".join(ls[i * len(ls) // n:(i + 1) * len(ls) // n]) for i in range(n)]
    else:
        w = t.split(); parts = [" ".join(w[i * len(w) // n:(i + 1) * len(w) // n]) for i in range(n)]
    return "\n\n".join(f"Section {i + 1}\n{p}" for i, p in enumerate(parts))


def _line_numbers_tf(t):
    c = [0]
    def f(l): c[0] += 1; return f"{c[0]}| {l}"
    return "\n".join(f(l) if l.strip() else l for l in lines(t))


def _highlight_tf(t):
    ls = lines(t); k = next(k for k, l in enumerate(ls) if l.strip())
    return "\n".join(ls[:k] + ["*" + ls[k].strip() + "*"] + ls[k + 1:])


# ------------------------------------------------------------------ graders
def _pref(prefix):
    bare = prefix.strip()
    return lambda t: (lambda ls: any(l.startswith(prefix) and l[len(prefix):].strip() for l in ls) and all(l == bare or l.startswith(prefix) for l in ls))(NE(t))
def _numbered(fmt):
    return lambda t: (lambda ls: len(ls) >= 1 and all(l.startswith(fmt(i)) and l[len(fmt(i)):].strip() for i, l in enumerate(ls, 1)))(NE(t))


def _fence(t):
    ls = NL(t.strip())
    return len(ls) >= 3 and bool(re.fullmatch(r"```[A-Za-z]*", ls[0])) and ls[-1] == "```" and not any(l.startswith("```") for l in ls[1:-1]) and any(l for l in ls[1:-1])


def _pipe(t):
    ok = two = False
    for l in NE(t):
        parts = l.split(" | ")
        if any((not p) or re.search(r"\s", p) for p in parts): return False      # a "|" that is itself a word of the text is a word
        ok = True; two |= len(parts) >= 2
    return ok and two


def _dbl(t):
    ls = NE(t); return bool(ls) and all(re.fullmatch(r"\S+(  \S+)*", l) for l in ls) and any("  " in l for l in ls)


_BT = r"(?:(?!<<|>>)\S)+"
def _bigram(t):
    ls = NE(t); return bool(ls) and all(re.fullmatch(rf"<<{_BT} {_BT}>>(?: <<{_BT} {_BT}>>)*(?: <<{_BT}>>)?|<<{_BT}>>", l) for l in ls)
def _five(t):
    ls = NE(t); return bool(ls) and all(len(l.split()) == 5 for l in ls[:-1]) and 1 <= len(ls[-1].split()) <= 5


def _mdh(t):
    n = 0; state = "start"; blanks = 0      # states: start, heading (expects its paragraph), body, gap (blank line after a paragraph)
    for l in NL(t):
        if not l:
            if state == "heading": blanks += 1
            elif state == "body": state = "gap"
            continue
        m = re.fullmatch(r"## Step (\d+)", l)
        if m:
            if int(m.group(1)) != n + 1 or state == "heading": return False
            n += 1; state = "heading"; blanks = 0; continue
        if l.startswith("#"): return False
        if state in ("start", "gap"): return False      # text before the first heading, or a second paragraph under one heading
        if state == "heading" and blanks > 1: return False
        state = "body"
    return n >= 1 and state in ("body", "gap")


def _brace(t):
    def one(l):
        if len(l) < 3 or l[0] != "{" or l[-1] != "}": return False
        d = 0
        for i, ch in enumerate(l):
            d += ch == "{"; d -= ch == "}"
            if d == 0 and i < len(l) - 1: return False
        return d == 0 and bool(l[1:-1].strip())
    ls = NE(t); return bool(ls) and all(one(l) for l in ls)


def _sections_gr(t):
    ls = NE(t); lab = [i for i, l in enumerate(ls) if re.fullmatch(r"Section \d+", l)]
    if [ls[i] for i in lab] != ["Section 1", "Section 2", "Section 3", "Section 4"] or lab[0] != 0: return False
    return all(b - a > 1 for a, b in zip(lab, lab[1:] + [len(ls)]))


def _upper_at(pick):
    def gr(t):
        ls = [l for l in nonempty(t) if re.search(W, l)]
        return len(ls) >= 1 and all((lambda x: x == x.upper())(pick(re.findall(W, l))) for l in ls)
    return gr


# ------------------------------------------------------------------ the rules added to the pool
# stage: where the transform runs in `apply`. Order inside a stage is the order of this dict.
def _r(kind, stage, ins, tf, gr, q=False): return dict(cls=kind, stage=stage, ins=ins, tf=tf, gr=gr, q=q)


# titles for title_angle: written in the row's language and chosen by the question, so neither a language row gets an
# English title nor every row the same one
TITLES = {"en": ["Reasoning steps", "Working it out", "Thinking it through", "Notes on the question", "Step-by-step reasoning", "Finding the answer"],
          "es": ["Pasos del razonamiento", "Resolviendo la pregunta", "Pensándolo bien", "Notas sobre la pregunta", "Razonamiento paso a paso", "Buscando la respuesta"],
          "fr": ["Étapes du raisonnement", "Résoudre la question", "Bien y réfléchir", "Notes sur la question", "Raisonnement pas à pas", "Trouver la réponse"],
          "ru": ["Шаги рассуждения", "Решаю вопрос", "Обдумываю всё", "Заметки по вопросу", "Пошаговое рассуждение", "Ищу ответ"],
          "pl": ["Kroki rozumowania", "Rozwiązuję pytanie", "Przemyślę to", "Notatki do pytania", "Rozumowanie krok po kroku", "Szukam odpowiedzi"]}


def title(t: str, q: str, lang: str = "en") -> str:
    import hashlib
    opts = TITLES.get(lang, TITLES["en"]); i = int(hashlib.sha1((q or "").encode()).hexdigest(), 16) % len(opts)
    return f"<<{opts[i]}>>\n" + t.lstrip()


RULES: dict[str, dict] = {
    "para_step_label": _r("paragraph", "pre", "Begin every paragraph with the label 'Step N:' where N counts paragraphs from 1.",
        lambda t: "\n\n".join(f"Step {i}: {p}" for i, p in enumerate(paras(t), 1)),
        lambda t: (lambda ps: len(ps) >= 1 and all(re.match(rf"Step {i}:(\s|$)", p) for i, p in enumerate(ps, 1)))(PS(t))),
    "para_end_mark": _r("paragraph", "pre", "End every paragraph with the marker '[end of step]'.",
        lambda t: "\n\n".join(p.rstrip() + " [end of step]" for p in paras(t)),
        lambda t: (lambda ps: len(ps) >= 1 and all(re.search(r"\S\s+\[end of step\]$", p) for p in ps))(PS(t))),
    "inc_arrow_summary": _r("inclusion", "pre", "Include at least one line that starts with '=>'.",
        lambda t: (lambda ps: "\n\n".join(ps[:-1] + ["=> " + ps[-1]]))(paras(t)),
        lambda t: any(l.startswith("=>") for l in NL(t))),
    "line_quote": _r("line-layout", "post", "Start every non-empty line with '> '.",
        lambda t: "\n".join("> " + l if l.strip() else l for l in lines(t)), _pref("> ")),
    "line_numbers": _r("line-layout", "post", "Number every non-empty line, counting only non-empty lines from 1: start each with its number and a bar, '1| ', '2| ', ...",
        _line_numbers_tf, _numbered(lambda i: f"{i}| ")),
    "wrap_tag": _r("whole-wrap", "post", "Put the whole reasoning between <notes> and </notes> tags.",
        lambda t: "<notes>\n" + t.strip() + "\n</notes>",
        lambda t: (lambda s: s.startswith("<notes>") and s.endswith("</notes>") and s.count("<notes>") == 1 and s.count("</notes>") == 1 and bool(s[7:-8].strip()))(t.strip())),
    "wrap_fence": _r("whole-wrap", "post", "Put the whole reasoning inside one fenced block: a line of three backticks before it and a line of three backticks after it.",
        lambda t: "```\n" + t.strip() + "\n```", _fence),
    "header_line": _r("whole-start", "post", "Make the first line exactly '=== REASONING ==='.",
        lambda t: "=== REASONING ===\n" + t.lstrip(),
        lambda t: t.replace("\r", "").split("\n")[0] == "=== REASONING ===" and len(NE(t)) >= 2),
    "footer_line": _r("whole-end", "post", "Make the last line exactly '=== END ==='.",
        lambda t: t.rstrip() + "\n=== END ===",
        lambda t: t.replace("\r", "").rstrip("\n").split("\n")[-1] == "=== END ===" and len(NE(t)) >= 2),
    "sent_count_trailer": _r("whole-end", "post", "Finish with a last line 'Lines: N', where N is the number of non-empty lines above that line (for example 'Lines: 12' after twelve non-empty lines).",
        lambda t: t.rstrip() + f"\nLines: {len(nonempty(t))}",
        lambda t: (lambda ls: len(ls) >= 2 and (lambda m: bool(m) and int(m.group(1)) == len(ls) - 1)(re.fullmatch(r"Lines: ([1-9][0-9]*)", ls[-1], re.A)))(NE(t))),
    "word_sep_pipe": _r("per-word", "post_word", "Separate the words on each line with ' | ' (space, bar, space) instead of a single space.",
        lambda t: _resep(t, " | "), _pipe),
    "double_space": _r("per-word", "post_word", "Put exactly two spaces between the words on each line instead of one.",
        lambda t: _resep(t, "  "), _dbl),
    "postscript": _r("whole-end", "post", "End with a postscript on its own last line, starting with 'P.S.'",
        lambda t: t.rstrip() + "\nP.S. The steps above were followed in order.",
        lambda t: bool(re.match(r"P\.S\.(\s|$)", (NE(t) or [""])[-1])) and len(NE(t)) >= 2),
    "title_angle": _r("whole-start", "post", "Give the reasoning a title on the first line, wrapped in double angular brackets, like <<title>>.",
        lambda t: f"<<{TITLES['en'][0]}>>\n" + t.lstrip(),        # apply() uses title() instead: row's language, one of six titles
        lambda t: bool(re.fullmatch(r"<<(?:(?!<<|>>).)*\w(?:(?!<<|>>).)*>>", (NE(t) or [""])[0])) and len(NE(t)) >= 2),
    "wrap_quotes": _r("whole-wrap", "post", "Wrap the entire reasoning in double quotation marks.",
        lambda t: '"' + t.strip() + '"',
        lambda t: (lambda s: len(s) > 2 and (s[0], s[-1]) in {('"', '"'), ("“", "”")} and bool(s[1:-1].strip()))(t.strip())),
    "bigram_wrap": _r("per-word", "post_word", "Wrap the words of every line in double angular brackets two at a time, like <<I am>> <<at home>>; a last single word gets its own brackets.",
        lambda t: "\n".join((lambda w: " ".join("<<" + " ".join(w[i:i + 2]) + ">>" for i in range(0, len(w), 2)))(l.split()) if l.strip() else l for l in lines(t)), _bigram),
    "html_paragraphs": _r("markup", "pre", "Wrap each paragraph in <p> and </p>.",
        lambda t: "\n\n".join("<p>" + p.strip() + "</p>" for p in paras(t)),
        lambda t: (lambda ps: len(ps) >= 1 and all(re.fullmatch(r"<p>(?:(?!</?p>).)*\S(?:(?!</?p>).)*</p>", p, re.S) for p in ps))(PS(t))),
    "five_words_per_line": _r("line-layout", "post", "Break the reasoning into lines of exactly five words each (the last line may be shorter); a word is anything between spaces.",
        lambda t: (lambda w: "\n".join(" ".join(w[i:i + 5]) for i in range(0, len(w), 5)))(t.split()), _five),
    "pilcrow_paragraphs": _r("paragraph", "pre", "Begin every paragraph with the marker '¶ '.",
        lambda t: "\n\n".join("¶ " + p.strip() for p in paras(t)),
        lambda t: (lambda ps: len(ps) >= 1 and all(p.startswith("¶ ") and p[2:].strip() for p in ps))(PS(t))),
    "para_end_sentence": _r("paragraph", "pre", "End every paragraph with the sentence 'This part is settled.'",
        lambda t: "\n\n".join(p.rstrip() + " This part is settled." for p in paras(t)),
        lambda t: (lambda ps: len(ps) >= 1 and all(re.search(r"\S\s+This part is settled\.$", p) for p in ps))(PS(t))),
    "md_headings": _r("block-structure", "pre", "Put a markdown heading '## Step k' on its own line directly above each paragraph, with k counting paragraphs from 1 and no text before the first heading.",
        lambda t: "\n\n".join(f"## Step {i}\n{p}" for i, p in enumerate(paras(t), 1)), _mdh),
    "line_bar": _r("line-layout", "post", "Begin every non-empty line with '| '.",
        lambda t: "\n".join("| " + l if l.strip() else l for l in lines(t)), _pref("| ")),
    "repeat_question": _r("whole-start", "first", "Begin the reasoning by copying the question word for word, then reason.",
        lambda t, q: q.strip() + "\n\n" + t.lstrip(),
        lambda t, q: " ".join(t.split()).startswith(" ".join(q.split())) and len(" ".join(t.split())) > len(" ".join(q.split())), q=True),
    "every_third_upper": _r("letter-case", "case", "Write every third word in capital letters (words 3, 6, 9, ...), counting through the whole reasoning without restarting at new lines and counting only tokens that contain a letter.",
        _third, lambda t: (lambda w: len(w) >= 3 and all(m.group(0) == m.group(0).upper() for i, m in enumerate(w, 1) if i % 3 == 0))(wtoks(t))),
    "kw_position": _r("word-position", "late", "Make the fifth word of the reasoning the word 'pivot' (a word is any token that contains a letter or digit).",
        lambda t: _ins_tok(t, 4, "pivot"), lambda t: (lambda w: len(w) >= 5 and w[4].lower() == "pivot")(ctoks(t))),
    "second_penultimate": _r("word-position", "late", "Make the second word and the second-to-last word of the reasoning the word 'verily' (a word is any token that contains a letter or digit).",
        lambda t: _ins_tok(_ins_tok(t, 1, "verily"), -2, "verily"),
        lambda t: (lambda w: len(w) >= 4 and w[1].lower() == "verily" and w[-2].lower() == "verily")(ctoks(t))),
    "line_index": _r("per-line", "pre", "Begin every non-empty line with its number in parentheses, counting only non-empty lines from 1: (1), (2), (3), ...",
        lambda t: map_lines(t, lambda l, i: f"({i}) {l}"), _numbered(lambda i: f"({i}) ")),
    "line_index_suffix": _r("per-line", "pre", "End every non-empty line with its number in the form (L1), (L2), (L3), ..., counting only non-empty lines from 1, with nothing after it.",
        lambda t: map_lines(t, lambda l, i: f"{l.rstrip()} (L{i})"),
        lambda t: (lambda ls: len(ls) >= 1 and all(re.search(rf"\S\s+\(L{i}\)$", l) for i, l in enumerate(ls, 1)))(NE(t))),
    "brace_lines": _r("per-line", "pre", "Enclose every non-empty line in curly braces.",
        lambda t: map_lines(t, lambda l, i: "{" + l.strip() + "}"), _brace),
    "line_first_upper": _r("letter-case", "case", "On every non-empty line, write the first word that contains letters in capital letters.",
        lambda t: map_lines(t, lambda l, i: _first_up(l)), _upper_at(lambda ws: ws[0])),
    "line_last_upper": _r("letter-case", "case", "On every non-empty line, write the last word that contains letters in capital letters.",
        lambda t: map_lines(t, lambda l, i: _last_up(l)), _upper_at(lambda ws: ws[-1])),
    "echo_first_line": _r("whole-end", "pre", "End the reasoning by repeating its first line word for word as the last line.",
        lambda t: t.rstrip() + "\n" + nonempty(t)[0],
        lambda t: (lambda ls: len(ls) >= 2 and ls[0].strip() == ls[-1].strip())(nonempty(t))),
    "italic_first_word": _r("markup", "pre", "Put the first word of every non-empty line in HTML italics, <i>like</i> this.",
        lambda t: map_lines(t, lambda l, i: re.sub(r"\S+", lambda m: "<i>" + m.group(0) + "</i>", l, count=1)),
        lambda t: (lambda ls: len(ls) >= 1 and all(re.match(r"<i>[^<\s]+</i>(\s|$)", l) for l in ls))(NE(t))),
    "highlight_first_line": _r("markup", "pre", "Highlight the first line with markdown asterisks, *like this*.",
        _highlight_tf,
        lambda t: (lambda l: len(l) > 2 and l.startswith("*") and l.rstrip().endswith("*") and "*" not in l.strip()[1:-1])((nonempty(t) or [""])[0])),
    "line_marker": _r("line-layout", "post", "Begin every non-empty line with the marker '!?!? '.",
        lambda t: "\n".join("!?!? " + l if l.strip() else l for l in lines(t)), _pref("!?!? ")),
    "inc_checkpoint3": _r("inclusion", "ins", "Include the marker '(checkpoint)' at least three times.",
        lambda t: add_at_lines(t, ["(checkpoint)"] * 3), lambda t: t.count("(checkpoint)") >= 3),
    "key_sentence_twice": _r("inclusion", "ins", "Include the sentence 'The plan is on track.' exactly twice.",
        lambda t: add_at_lines(t, ["The plan is on track."] * max(0, 2 - t.count("The plan is on track."))),
        lambda t: t.count("The plan is on track.") == 2 and len(re.findall(r"(?:^|(?<=\s))The plan is on track\.(?=\s|$)", t)) == 2),
    "kw_counts": _r("inclusion", "ins", "Include the word 'tally' exactly once, 'ledger' exactly twice and 'onward' exactly three times. Capital and small letters both count.",
        lambda t: add_at_lines(t, ["Tally."] * max(0, 1 - _kw("tally", t)) + ["Ledger."] * max(0, 2 - _kw("ledger", t)) + ["Onward."] * max(0, 3 - _kw("onward", t))),
        lambda t: (_kw("tally", t), _kw("ledger", t), _kw("onward", t)) == (1, 2, 3)),
    # "at least" versions of the three exact-count rules (25 November): these are trained, the exact versions are held out.
    # A remark that names the word then does not break the rule, so remarks can be copied as the base model wrote them.
    "key_sentence_min": _r("inclusion", "ins", "Include the sentence 'The plan is on track.' at least twice.",
        lambda t: add_at_lines(t, ["The plan is on track."] * max(0, 2 - len(KEY_SENTENCE.findall(_free(t))))),
        lambda t: len(KEY_SENTENCE.findall(t)) >= 2),
    "kw_counts_min": _r("inclusion", "ins", "Include the word 'tally' at least once, 'ledger' at least twice and 'onward' at least three times. Capital and small letters both count.",
        lambda t: (lambda f: add_at_lines(t, ["Tally."] * max(0, 1 - _kw("tally", f)) + ["Ledger."] * max(0, 2 - _kw("ledger", f)) + ["Onward."] * max(0, 3 - _kw("onward", f))))(_free(t)),
        lambda t: _kw("tally", t) >= 1 and _kw("ledger", t) >= 2 and _kw("onward", t) >= 3),
    "hence_min": _r("inclusion", "ins", 'Use the word "hence" at least twice in your chain of thought (your step-by-step reasoning). Capital and small letters both count.',
        lambda t: _hence(t, free=True), lambda t: len(re.findall(r"\bhence\b", t, re.I)) >= 2),
    "sections_numbered": _r("block-structure", "pre", "Divide the reasoning into four sections and begin each with a line that is exactly 'Section 1', 'Section 2', 'Section 3', 'Section 4', each followed by its text.",
        _sections_tf, _sections_gr),
}
NEW = list(RULES)

# ------------------------------------------------------------------ the pool
# existing rules whose edit and grader are code only
OLD = ["rif:capital", "cc:uppercase_thinking", "rw:all_caps", "cc:lowercase_thinking", "rw:all_lower", "rw:initial_caps", "rw:include_therefore",
       "rw:include_marker_note", "rw:include_quote_marker", "rw:include_exactly_twice", "rif:end_checker", "rw:start_with_phrase", "cc:repeat_sentences",
       "ifb:start_end_same", "ifb:square_brackets", "rw:xml_steps", "cc:json_format", "rw:section_headers", "cc:alternating_case", "rif:end_of_sentence",
       "cc:end_of_sentence", "ifb:emoji_end", "ifb:first_word_sent", "ifb:conjunctions"]
LANG_NAME = {"es": "Spanish", "fr": "French", "ru": "Russian", "pl": "Polish", "en": "English"}
LANGS = ["lang:es", "lang:fr", "lang:ru", "lang:pl"]          # non-English languages; "lang:en" needs no edit
ALL = OLD + NEW + LANGS
# extra wordings of one rule: a bundle holds at most one, a row draws one wording
DUPW = {"cc:uppercase_thinking": "rif:capital", "rw:all_caps": "rif:capital", "rw:all_lower": "cc:lowercase_thinking", "cc:end_of_sentence": "rif:end_of_sentence"}
# programmatic rules held out for testing
HELD = {"cc:alternating_case", "rif:end_of_sentence", "cc:end_of_sentence", "ifb:emoji_end", "ifb:first_word_sent", "ifb:conjunctions",     # kept from earlier runs
        "line_numbers", "wrap_fence", "postscript", "brace_lines",                                                                         # a trained near neighbour exists
        "kw_position", "second_penultimate",                                                                                               # whole kind held out
        "cc:json_format", "wrap_tag", "html_paragraphs", "rw:xml_steps", "cc:repeat_sentences",                                            # fit in almost no bundle
        "echo_first_line", "italic_first_word", "rw:section_headers", "md_headings", "para_step_label", "sections_numbered", "highlight_first_line",   # too rare in a draw
        "ifb:square_brackets",                                                                                                              # about 1,760 extra tokens per trace
        "kw_counts", "key_sentence_twice", "rw:include_exactly_twice"}                                                                      # exact counts; the "at least" versions are trained
TRAIN = [c for c in ALL if c not in DUPW and c not in HELD]
INSERTS = {"rw:include_exactly_twice", "rw:include_therefore", "kw_counts", "rw:include_quote_marker", "rw:include_marker_note", "inc_checkpoint3", "key_sentence_twice", "inc_arrow_summary",
           "hence_min", "kw_counts_min", "key_sentence_min"}
# an "at least" rule behaves like its exact version in every exclusion
SAME_AS = {"key_sentence_min": "key_sentence_twice", "kw_counts_min": "kw_counts", "hence_min": "rw:include_exactly_twice"}

# ------------------------------------------------------------------ which rules may share a bundle
FULLCASE = {"rif:capital", "cc:uppercase_thinking", "rw:all_caps", "cc:lowercase_thinking", "rw:all_lower", "rw:initial_caps", "cc:alternating_case"}
PARTCASE = {"line_first_upper", "line_last_upper", "every_third_upper"}
DUP = [{"rif:end_of_sentence", "cc:end_of_sentence"}, {"word_sep_pipe", "double_space"}, {"line_quote", "line_bar", "line_numbers", "line_marker", "line_index"}]
REWRITE = FULLCASE | PARTCASE | {"word_sep_pipe", "double_space", "ifb:square_brackets", "bigram_wrap", "five_words_per_line"}      # change words, spacing or line breaks everywhere
VERBATIM = {"key_sentence_twice", "para_end_sentence", "rw:start_with_phrase", "repeat_question", "rif:end_checker", "cc:repeat_sentences", "sections_numbered",
            "para_step_label", "md_headings", "header_line", "footer_line", "sent_count_trailer", "title_angle", "inc_checkpoint3", "para_end_mark", "rw:section_headers",
            "postscript", "wrap_tag", "rw:xml_steps", "html_paragraphs", "italic_first_word", "cc:json_format", "rw:include_marker_note", "kw_position", "second_penultimate"}   # need exact text
LINE_START = {"line_quote", "line_bar", "line_marker", "line_index", "line_numbers", "pilcrow_paragraphs", "para_step_label", "italic_first_word", "line_first_upper",
              "chain_lines", "html_paragraphs", "rw:xml_steps", "brace_lines", "md_headings", "sections_numbered", "rw:section_headers", "ifb:first_word_sent"}
TEXT_START = {"repeat_question", "rw:start_with_phrase", "header_line", "title_angle", "cc:repeat_sentences", "ifb:start_end_same", "highlight_first_line", "kw_position", "second_penultimate"}
LINE_END = {"line_index_suffix", "line_last_upper", "para_end_mark", "para_end_sentence", "html_paragraphs", "rw:xml_steps", "brace_lines", "rif:end_of_sentence", "cc:end_of_sentence", "ifb:emoji_end"}
TEXT_END = {"rif:end_checker", "footer_line", "sent_count_trailer", "echo_first_line", "ifb:start_end_same", "cc:repeat_sentences", "postscript", "second_penultimate"}
WRAP = {"wrap_tag", "wrap_quotes", "wrap_fence", "cc:json_format"}
PREFIX = {"line_quote", "line_bar", "line_marker", "line_index", "line_numbers", "pilcrow_paragraphs"}
EXACT_LINE = {"header_line", "footer_line", "title_angle", "sent_count_trailer", "postscript", "md_headings", "sections_numbered", "rw:section_headers", "echo_first_line"}
UPPER = {"rif:capital", "cc:uppercase_thinking", "rw:all_caps"}; UPPER_TEXT = {"header_line", "footer_line", "rif:end_checker", "rw:include_marker_note"}
NO_SPACE_TEXT = {"inc_checkpoint3", "rw:include_marker_note"}
ANGLE = {"rw:include_quote_marker", "title_angle", "line_quote", "inc_arrow_summary"}
# pairs that failed on every trace in the pair test, each with a stated reason
EXPLICIT = {tuple(k.split("|")): v for k, v in json.load(open(Path(__file__).with_name("programmatic_exclusions.json"))).items()}


def allowed(a: str, b: str) -> bool:
    """May rules a and b share a bundle. Pairs this allows must still pass the pair test (scripts/check_programmatic_pool.py)."""
    a, b = SAME_AS.get(a, a), SAME_AS.get(b, b)
    if a == b: return False                                   # a rule and its "at least" version, or the same rule twice
    if (a, b) in EXPLICIT or (b, a) in EXPLICIT: return False
    if a.startswith("lang:") and b.startswith("lang:"): return False
    if a in FULLCASE and b in FULLCASE | PARTCASE: return False
    if b in FULLCASE and a in PARTCASE: return False
    if any(a in d and b in d for d in DUP): return False
    for x, y in ((a, b), (b, a)):
        if x in UPPER and y in UPPER_TEXT: continue          # the required text is already in capitals
        if x in {"word_sep_pipe", "double_space"} and y in NO_SPACE_TEXT: continue   # the required text has no space inside
        if x in VERBATIM and y in REWRITE: return False
        if x in WRAP and y in WRAP | LINE_START | TEXT_START | LINE_END | TEXT_END: return False
        if x == "inc_arrow_summary" and y in LINE_START: return False
        if x == "bigram_wrap" and y in ANGLE: return False
        if x == "ifb:square_brackets" and y in ANGLE: return False
        if x == "five_words_per_line" and y in LINE_START | LINE_END | TEXT_START | TEXT_END | WRAP | {"inc_arrow_summary"}: return False   # it reflows every line and paragraph
        if x in {"word_sep_pipe", "double_space"} and y in PREFIX: return False   # the prefix would itself be treated as a word
        if x in PREFIX | {"line_index_suffix", "italic_first_word", "brace_lines"} and y in EXACT_LINE: return False   # every line against one exact line
    S = LINE_START | TEXT_START; E = LINE_END | TEXT_END
    if a in S and b in S: return False
    if a in E and b in E: return False
    return True


# ------------------------------------------------------------------ instructions
ANY_CASE = " Capital and small letters both count."


def instruction(c: str, a: dict) -> str:
    """The one source of a rule's instruction text; training prompts and base-model measurements must both use it."""
    if c.startswith("lang:"): return f"Write the reasoning in {LANG_NAME[c.split(':')[1]]}."
    if c in P.CONDS:
        s = P.instruction(c, a).split(" This requirement applies")[0]
        return s + ANY_CASE if c in ("rw:include_therefore", "rw:include_exactly_twice") else s
    return RULES[c]["ins"]


# ------------------------------------------------------------------ apply
def question(r: dict) -> str: return r["prompt"].split("Here is the question:\n\n", 1)[-1]
def _tf(k, t, q): return RULES[k]["tf"](t, q) if RULES[k]["q"] else RULES[k]["tf"](t)
def _gr(k, t, q): return RULES[k]["gr"](t, q) if RULES[k]["q"] else RULES[k]["gr"](t)


def _initial_caps(t: str) -> str:
    """Capital first letter for every word; a token that starts with a digit ("70s", "3rd") is left as it is."""
    def cap(tok):
        m = re.match(r"[^\w]*", tok); i = m.end()
        return tok[:i] + tok[i].upper() + tok[i + 1:] if i < len(tok) and tok[i].isalpha() else tok
    return "".join(p if k % 2 else cap(p) for k, p in enumerate(re.split(r"(\s+)", t)))


_OWN_INSERTS = ("rw:include_exactly_twice", "rw:include_therefore")
def _hence(t: str, free: bool = False) -> str:
    """Top up "hence" to two as one-word sentences inside a line; the model's own words are never replaced.
    free=True (the "at least" rule): occurrences inside remark sentences are not counted, so two real uses are always there.
    free=False (the exact rule): every occurrence counts, because the grader counts every occurrence."""
    need = 2 - len(re.findall(r"\bhence\b", _free(t) if free else t, re.I))
    return add_at_lines(t, ["Hence."] * need) if need > 0 else t


def _connectives(t: str, old: list[str]) -> str:
    """ "hence" (exact rule: topped up to two; more than two is left for the grader to fail) and "therefore" (added if absent)."""
    if "rw:include_exactly_twice" in old: t = _hence(t)
    if "rw:include_therefore" in old and not re.search(r"\btherefore\b", _free(t), re.I): t = add_at_lines(t, ["Therefore."])
    return t


def _insert_stage(bundle: list[str], r: dict, keep_clear) -> tuple[str, list[str], dict, tuple]:
    """Everything that inserts a required word, sentence or marker. Returns the text with the remark ranges still marked."""
    q = question(r); t = r["reasoning"]
    old = [c for c in P.CONDS if c in bundle]; a = P.finish_args(old, {}, q, t)
    own = _OWN_INSERTS
    if keep_clear:
        for x, y in sorted(keep_clear, reverse=True): t = t[:x] + KEEP_A + t[x:y] + KEEP_B + t[y:]
        # with remarks in the text the two marker rules are placed here, not by the pool: the pool treats a marker that a
        # remark merely mentions as the use of it, and would place [[NOTE]] without regard to the marked ranges
        own = _OWN_INSERTS + ("rw:include_marker_note", "rw:include_quote_marker")
        if "rw:include_marker_note" in old and "[[NOTE]]" not in _free(t): t = add_at_lines(t, ["[[NOTE]]"])
        if "rw:include_quote_marker" in old and ">>>" not in _free(t):
            ls = lines(t); full = [i for i, l in enumerate(ls) if l.strip()]; j = full[len(full) // 2]; ls[j] = ">>> " + ls[j]; t = "\n".join(ls)
    t = _connectives(t, old)                        # "hence" and "therefore", topped up without touching words already there
    for k in NEW:
        if k in bundle and RULES[k]["stage"] == "ins": t = _tf(k, t, q)
    return t, old, a, own


# what each insert rule must reach OUTSIDE remark sentences, so that naming a string in a remark never counts as using it
REAL_USE = {"hence_min": lambda f: len(re.findall(r"\bhence\b", f, re.I)) >= 2,
            "kw_counts_min": lambda f: _kw("tally", f) >= 1 and _kw("ledger", f) >= 2 and _kw("onward", f) >= 3,
            "key_sentence_min": lambda f: len(KEY_SENTENCE.findall(f)) >= 2,
            "rw:include_therefore": lambda f: bool(re.search(r"\btherefore\b", f, re.I)),
            "rw:include_marker_note": lambda f: "[[NOTE]]" in f,
            "rw:include_quote_marker": lambda f: ">>>" in f,
            "inc_checkpoint3": lambda f: f.count("(checkpoint)") >= 3}


def real_use_problems(bundle: list[str], r: dict, keep_clear) -> list[str]:
    """Insert rules of the bundle whose required word, sentence or marker is not fully present outside the remark ranges."""
    t, _, _, _ = _insert_stage(bundle, r, keep_clear); f = _free(t)
    return [c for c in bundle if c in REAL_USE and not REAL_USE[c](f)]


def apply(bundle: list[str], r: dict, keep_clear: list[tuple[int, int]] | None = None) -> tuple[str, dict]:
    """Apply every rule of the bundle to r["reasoning"] (already translated for a language row; language rules are skipped here).
    keep_clear: character ranges of r["reasoning"] (remark sentences) that inserted strings must stay out of and not sit between."""
    q = question(r); t, old, a, own = _insert_stage(bundle, r, keep_clear)
    t = t.replace(KEEP_A, "").replace(KEEP_B, "")
    t = P.inclusions(t, [c for c in old if c not in own])   # the pool's other inserts ([[NOTE]], >>>, conjunctions)
    for st in ("first", "pre"):
        for k in NEW:
            if k in bundle and RULES[k]["stage"] == st: t = _tf(k, t, q)
    t = P.per_sentence(t, old, a); t = P.structure(t, old); t = P.position(t, old, a)   # rest of pool.surface, same order
    if "ifb:square_brackets" in old: t = P.brackets(t)
    if "rw:initial_caps" in old: t = _initial_caps(t)        # the pool's version also capitalises "70s" to "70S"
    t = P.case(t, [c for c in old if c != "rw:initial_caps"])
    lang = next((c.split(":", 1)[1] for c in bundle if c.startswith("lang:")), "en")
    for st in ("post", "late", "post_word", "case"):
        for k in NEW:
            if k in bundle and RULES[k]["stage"] == st: t = title(t, q, lang) if k == "title_angle" else _tf(k, t, q)
    return t, a


# ------------------------------------------------------------------ graders for existing rules
def _xml_ok(t):
    s = t.strip(); blocks = re.findall(r"<step>(.*?)</step>", s, re.S)
    return len(blocks) >= 1 and all(b.strip() and "<step>" not in b for b in blocks) and not re.sub(r"<step>.*?</step>", "", s, flags=re.S).strip()


def _json_ok(t):
    s = t.strip()
    for p in ("```json", "```Json", "```JSON", "```"): s = s.removeprefix(p)
    s = s.removesuffix("```").strip()
    try: v = json.loads(s)
    except ValueError: return False
    return isinstance(v, (dict, list)) and len(v) > 0


def _sections_ok(t, a):
    ls = [l.strip() for l in t.replace("\r", "").split("\n") if l.strip()]; lab = [i for i, l in enumerate(ls) if l.startswith(("Given:", "Work:", "Check:"))]
    if [ls[i].split(":")[0] for i in lab] != ["Given", "Work", "Check"] or lab[0] != 0: return False
    return all(ls[i].split(":", 1)[1].strip() or j - i > 1 for i, j in zip(lab, lab[1:] + [len(ls)]))


def _cased(t): return any(ch.lower() != ch.upper() for ch in t)
# exact checks applied in addition to the pool's own grader
EXTRA = {"rw:start_with_phrase": lambda t, a: bool(re.match(r"Let me work through this\.(\s|$)", t.lstrip())),
         "rif:end_checker": lambda t, a: bool(re.search(r"(^|[^\w])" + re.escape(a["end_phrase"]) + r"$", t.rstrip())),
         "rw:include_marker_note": lambda t, a: "[[NOTE]]" in t,
         "rw:include_quote_marker": lambda t, a: bool(re.search(r"(?<!>)>>>(?!>)", t)),
         "rw:section_headers": _sections_ok,
         "rw:xml_steps": lambda t, a: _xml_ok(t), "cc:json_format": lambda t, a: _json_ok(t),
         "cc:uppercase_thinking": lambda t, a: _cased(t), "cc:lowercase_thinking": lambda t, a: _cased(t),
         "cc:repeat_sentences": lambda t, a: t.count("This reasoning is not suspicious.") >= 2,
         "ifb:start_end_same": lambda t, a: t.rstrip()[-1:].isalnum()}
# these three pool scorers ignore text inside code fences and between dollar signs; replaced by whole-text tests
OVERRIDE = {"rw:all_caps": lambda t, a: _cased(t) and t == t.upper(),
            "rw:all_lower": lambda t, a: _cased(t) and t == t.lower(),
            "rw:initial_caps": lambda t, a: (lambda ws: len(ws) >= 1 and all(w[0] == w[0].upper() for w in ws))([w for w in (re.sub(r"^[^\w]+", "", x) for x in t.split()) if w and w[0].isalpha()])}

# ------------------------------------------------------------------ language grader
# fixed English strings that rules insert; a language row keeps them in English and the language grader ignores them
LIT = ["The plan is on track.", "This part is settled.", "Hence", "Therefore", "Let me work through this.", "THIS THOUGHT PROCESS WAS GENERATED BY AI",
       "THIS EXPLANATION IS AI-GENERATED", "This reasoning is not suspicious.", "Section 1", "Section 2", "Section 3", "Section 4", "Step", "checkpoint", "Tally", "Ledger", "Onward",
       "Given", "Work", "Check", "REASONING", "END", "Lines", "P.S. The steps above were followed in order.", "pivot", "verily", "Indeed", "safe", *TITLES["en"], "NOTE",
       "and", "but", "or", "nor", "for", "so", "yet"]


def lang_mask(text: str, literals=(), question: str = "") -> str:
    """The text with everything removed that is allowed to stay in English in a language row: the bundle's fixed strings,
    the copied question, quoted material, code, formulas, links (the spans the translator also leaves alone) and markup."""
    from .translate import spans
    def drop(l):
        out = []; p = 0
        for x, y in spans(l): out.append(l[p:x]); p = y
        return " ".join(out + [l[p:]])
    t = "\n".join(drop(l) for l in text.split("\n"))
    for s in sorted([question.strip()] + list(literals), key=len, reverse=True):
        if s: t = re.sub(r"\b" + r"\W+".join(re.escape(w) for w in re.findall(r"\w+", s)) + r"\b", " ", t, flags=re.I) if re.search(r"\w", s) else t.replace(s, " ")
    t = re.sub(r"</?[A-Za-z]{1,12}>", " ", t)                       # real tags only, not <<word pairs>>
    t = re.sub(r"[\[\]{}|<>*#=`¶]", " ", t)                          # markers
    return re.sub(r"[ \t]+", " ", t).strip()


def _chunks(m: str, size: int = 25) -> list[str]:
    """Pieces of about `size` words, cut at sentence ends, so one sentence in another language is noticed."""
    out = []; cur = []
    for s in re.split(r"(?<=[.!?…])\s+|\n+", m):
        if not s.strip(): continue
        cur.append(s.strip())
        if len(" ".join(cur).split()) >= size: out.append(" ".join(cur)); cur = []
    if cur:
        if out and len(" ".join(cur).split()) < size // 2: out[-1] += " " + " ".join(cur)
        else: out.append(" ".join(cur))
    return out


def _lang_score(text: str) -> tuple[str | None, float]:
    from fast_langdetect import detect
    try:
        try: r = detect(text, low_memory=False)
        except TypeError: r = detect(text)
    except Exception: return None, 0.0
    if isinstance(r, list): r = r[0] if r else None
    return (r["lang"], float(r.get("score", 1.0))) if r else (None, 0.0)


def lang_ok(text: str, lang: str, literals=(), question: str = "") -> bool:
    """The text is in `lang`: the whole is detected as it and, for a non-English language, no piece is confidently English."""
    m = lang_mask(text, literals, question).lower()
    if len(re.findall(r"\w+", m)) < 3: return False
    d, _ = _lang_score(re.sub(r"\s+", " ", m))
    if d is not None and d != lang: return False
    if lang == "en": return True
    ch = [c for c in _chunks(m) if len(re.findall(r"[^\W\d_]{2,}", c)) >= 12]
    # a piece counts against the text only if it is confidently English: short pieces of Spanish or Polish are often
    # mistaken for a neighbouring language, a list of product names can look English, and the failure this guards
    # against is slipping back into English
    return not any((lambda x: x[0] == "en" and x[1] >= EN_CONFIDENCE)(_lang_score(c)) for c in ch)


EN_CONFIDENCE = 0.8
# ------------------------------------------------------------------ grade
def grade_one(c: str, t: str, a: dict, q: str) -> bool:
    """Exact pass or fail for rule c on the final text t. a: the row's args from `apply`; q: the question."""
    if not t or not t.strip(): return False
    if c.startswith("lang:"): return lang_ok(t, c.split(":")[1], LIT + [str(v) for v in a.values() if isinstance(v, str)], q)
    if c in OVERRIDE: return bool(OVERRIDE[c](t, a))
    if c in P.CONDS: return bool(P.grade(c, t, a)) and (c not in EXTRA or bool(EXTRA[c](t, a)))
    return bool(_gr(c, t, q))


def grade_all(bundle: list[str], t: str, a: dict, q: str) -> list[str]:
    """The rules of the bundle that fail on t (empty list: the row is good)."""
    return [c for c in bundle if c != "lang:en" and not grade_one(c, t, a, q)]


# ------------------------------------------------------------------ check stamp
# A draw is only valid for the traces it was checked on and for the rule code it was checked with. The pool check writes a
# stamp next to the draw; the build refuses to run if the stamp is missing or does not match (scripts/check_programmatic_pool.py).
def file_sha(path) -> str:
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def code_sha() -> str:
    """One hash over the files that decide what a rule does: rules, exclusions, the pool's transforms and the translator."""
    import hashlib
    here = Path(__file__).parent; h = hashlib.sha1()
    for n in ("programmatic.py", "programmatic_exclusions.json", "pool.py", "translate.py"): h.update(file_sha(here / n).encode())
    return h.hexdigest()


def stamp_problems(draw_path, rollouts_path) -> list[str]:
    """Reasons why this draw must not be built from these traces with the current code (empty list: fine)."""
    sp = Path(draw_path).with_name("check.json")
    if not sp.exists(): return [f"no check stamp next to the draw ({sp}): the pool has not been checked for this model"]
    st = json.load(open(sp)); out = []
    if st.get("draw_sha") != file_sha(draw_path): out.append("the draw file has changed since it was checked")
    if st.get("rollouts_sha") != file_sha(rollouts_path): out.append("the source traces are not the ones the draw was checked on (another model, or a regenerated file)")
    if st.get("code_sha") != code_sha(): out.append("the rule code has changed since the draw was checked")
    if not st.get("passed"): out.append("the last check did not pass: " + "; ".join(st.get("failures", [])[:3]))
    return out
