"""Self-contained tests for the programmatic rule pool (src/cotctl/sft/programmatic.py). No model, no network."""
import itertools
import pytest
from cotctl.sft import programmatic as G

QUESTION = "Which of the three rooms in the old library holds the map collection?"
# plain descriptive text in several paragraphs and lines, with a quote, a number and a short list
TEXT = """The library has three rooms on the ground floor. The first room holds the newspapers and the second holds the atlases.

A sign near the stairs says "Maps are kept in the east room." The east room is the third one, next to the garden door.

The catalogue lists 240 maps in total. So the map collection is in the third room.

1. Newspapers are in the first room.
2. Atlases are in the second room.

Thus the answer is the third room."""
PROMPT = "Think step-by-step.\n\nHere is the question:\n\n" + QUESTION
ROW = {"prompt": PROMPT, "reasoning": TEXT}
CODE_RULES = [c for c in G.ALL if not c.startswith("lang:")]
# rules whose benchmark grader depends on a sentence splitter that this sample text is not written for
SKIP_ALONE = {"rif:end_of_sentence", "cc:end_of_sentence", "ifb:emoji_end", "ifb:first_word_sent"}


def test_pool_is_consistent():
    assert set(G.TRAIN).isdisjoint(G.HELD)
    assert set(G.HELD) <= set(G.ALL) and set(G.DUPW) <= set(G.ALL) and set(G.DUPW.values()) <= set(G.ALL)
    assert all(c in G.RULES for c in G.SAME_AS) and all(v in G.ALL for v in G.SAME_AS.values())
    assert len(G.TRAIN) >= 30


@pytest.mark.parametrize("rule", [c for c in CODE_RULES if c not in SKIP_ALONE])
def test_transform_satisfies_its_own_grader(rule):
    text, args = G.apply([rule], ROW)
    assert G.grade_one(rule, text, args, QUESTION), f"{rule}: its own transform does not pass its grader\n{text[:300]}"


@pytest.mark.parametrize("rule", CODE_RULES)
def test_empty_text_never_passes(rule):
    _, args = G.apply([rule], ROW)
    assert not G.grade_one(rule, "", args, QUESTION) and not G.grade_one(rule, "  \n ", args, QUESTION)


@pytest.mark.parametrize("rule", G.TRAIN)
def test_every_training_rule_has_an_instruction(rule):
    _, args = G.apply([c for c in [rule] if not c.startswith("lang:")], ROW)
    ins = G.instruction(rule, args)
    assert isinstance(ins, str) and len(ins.split()) >= 4


def test_allowed_is_symmetric_and_never_pairs_a_rule_with_itself():
    for a, b in itertools.combinations(G.ALL, 2): assert G.allowed(a, b) == G.allowed(b, a)
    for a, b in G.SAME_AS.items(): assert not G.allowed(a, b)
    assert not G.allowed("lang:es", "lang:fr")


def test_untranslated_rows_only_add_words():
    import re
    from collections import Counter
    words = lambda t: Counter(w.lower() for w in re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", t))
    bundle = ["hence_min", "kw_counts_min", "key_sentence_min", "rw:include_therefore", "inc_checkpoint3", "para_end_mark", "header_line"]
    text, args = G.apply(bundle, ROW)
    assert not G.grade_all(bundle, text, args, QUESTION)
    assert not (words(TEXT) - words(text)), "a word of the source is missing from the target"
    assert "Thus the answer" in text and "So the map collection" in text, "a sentence-opening So or Thus was replaced"


def test_inserts_stay_out_of_marked_remarks_and_do_not_count_them():
    remark = "I must use the words 'tally', \"ledger\" and onward, plus hence, and the sentence 'The plan is on track.' twice."
    lines = TEXT.split("\n"); lines[2] = lines[2] + " " + remark; text0 = "\n".join(lines); a0 = text0.index(remark)
    bundle = ["hence_min", "kw_counts_min", "key_sentence_min", "rw:include_therefore"]
    text, args = G.apply(bundle, {"prompt": PROMPT, "reasoning": text0}, keep_clear=[(a0, a0 + len(remark))])
    assert remark in text and not G.grade_all(bundle, text, args, QUESTION)
    outside = text.replace(remark, "")
    assert len(G.KEY_SENTENCE.findall(outside)) >= 2 and outside.lower().count("hence") >= 2 and outside.lower().count("ledger") >= 2
    assert G.KEEP_A not in text and G.KEEP_B not in text


def test_exact_graders_reject_near_misses():
    a = {}
    assert not G.grade_one("header_line", " === REASONING ===\ntext", a, QUESTION)
    assert not G.grade_one("key_sentence_min", "The plan is on TRACK. The plan is on track. x", a, QUESTION)
    assert not G.grade_one("sent_count_trailer", "a\nb\nLines: 3", a, QUESTION) and G.grade_one("sent_count_trailer", "a\nb\nLines: 2", a, QUESTION)
    assert not G.grade_one("line_index", "(1) a\n(3) b", a, QUESTION) and G.grade_one("line_index", "(1) a\n\n(2) b", a, QUESTION)
    assert not G.grade_one("repeat_question", "Some text. " + QUESTION, a, QUESTION)
    assert not G.grade_one("wrap_fence", "```a b```", a, QUESTION)


def test_translator_helpers_need_no_model():
    from cotctl.sft.translate import sentences, spans, LIST_MARK, lost_list_marks
    assert sentences("A book by J.K. Rowling is here. Dr. Smith agrees.") == ["A book by J.K. Rowling is here.", "Dr. Smith agrees."]
    line = 'I will post "A great read! What a book." and tag #books at 3^2 = 9.'
    kept = [line[x:y] for x, y in spans(line)]
    assert '"A great read! What a book."' in kept and "#books" in kept and any("3^2 = 9" in k for k in kept)
    assert LIST_MARK.match("2. Atlases") and LIST_MARK.match("- item") and not LIST_MARK.match("2024 was a year")
    assert lost_list_marks("1. a\n2. b", "1. x\ny") == ["2. b"] and lost_list_marks("1. a\n2. b", "1. x\n2. y") == []


def test_a_marker_named_in_a_remark_is_still_really_used():
    remark = 'I also need to include the exact marker >>> somewhere and the marker [[NOTE]], and "(checkpoint)" three times.'
    lines = TEXT.split("\n"); lines[0] = lines[0] + " " + remark; text0 = "\n".join(lines); a0 = text0.index(remark); spans = [(a0, a0 + len(remark))]
    bundle = ["rw:include_quote_marker", "rw:include_marker_note", "inc_checkpoint3", "hence_min"]; row = {"prompt": PROMPT, "reasoning": text0}
    text, args = G.apply(bundle, row, keep_clear=spans)
    assert remark in text and not G.grade_all(bundle, text, args, QUESTION)
    outside = text.replace(remark, "")
    assert ">>>" in outside and "[[NOTE]]" in outside and outside.count("(checkpoint)") >= 3
    assert G.real_use_problems(bundle, row, spans) == []
