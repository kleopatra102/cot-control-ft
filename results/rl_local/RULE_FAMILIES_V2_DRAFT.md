# Rule families with random values (draft for review, not built)

Draft, 26 November 2026; motivation updated 27 November 2026 with the full evaluation. Nothing here has been implemented.
It proposes the next version of the programmatic rules, because the treated adapters generalise only to close relatives
of the trained rules.

## 1. Why

### What the full evaluation showed

Both R1 models, Gemini-data adapters, 50 prompts per rule (PROG_EVAL_G_RESULTS.md):

| | R1-Distill-Qwen-7B | R1-Distill-Llama-8B |
|---|---|---|
| Trained rules, control -> treated | 8.5% -> 35.5%, gain 0.30 | 7.4% -> 29.4%, gain 0.24 |
| Held-out rules, control -> treated | 1.6% -> 11.4%, gain 0.10 [0.03, 0.18] | 3.0% -> 4.8%, gain 0.02 [-0.04, 0.09] |
| Held-out rules up 10+ points | 5 of 27 | 2 of 27 |
| Bundles with every rule met | 0% | 0% |

- **Transfer reaches only near relatives.** On Qwen, four structural labelling rules give 80% of the held-out gain:
  "Step N:" paragraph labels, numbered lines, "## Step k" headings, Given/Work/Check sections. They are close to trained
  rules (line prefixes and indices, paragraph markers, header lines). Llama transfers only to "Step N:" labels.
- **New kinds of operation do not transfer.** Character- and word-level rules, markup and exact counts stay at 0% on
  both models.
- **Some trained rules are not learned either.** Every third word in capitals, five words per line, double spaces and
  same first and last word stay near 0% after training. "The plan is on track." at least twice falls (Qwen -16,
  Llama -30 points).
- **No arm meets every rule of a bundle**, so the model has not learned to combine rules.
- The NLLB pilot had reported no held-out transfer only because it reached 13 held-out rules, all among those still
  at 0%.

### What we checked first

We suspected the model wrote memorised strings without reading the prompt. It does not. On prompts that did not ask
for a string, the treated model wrote that trained string in 0.0% of rollouts (pilot adapters). This held for
"tally/ledger/onward", "The plan is on track.", "(checkpoint)", "[[NOTE]]", ">>>", "[end of step]", headers, footers,
(L1) and '!?!? '. It covered all 200 prompts without rules and 621 held-out-rule prompts. So the model does read which
rule is asked.

### What we conclude

The model has learned 39 behaviours, each tied to its instruction. These extend to rules of the same kind (a new way to
label lines or paragraphs) but not to a new kind of operation. In instruction tuning, transfer to unseen tasks grows
with the number of distinct tasks seen. 39 fixed rules, each always with the same strings, is few tasks, and several
kinds of operation have no working example in training.

### What this draft does

It aims for many distinct tasks:
- rule families with random values;
- several wordings per rule;
- opposite qualifiers;
- a mix of 1 to 7 rules per row;
- every kind of operation covered in training.

Everything is still applied by code and graded by code.

## 2. Design

- **Family.** A function `apply(text, params)` and a grader `grade(text, params)`, as now. The params are drawn per
  row from pools, so the model has to read the instruction to know what to write.
- **Wordings.** Each family has 3 to 5 hand-written instruction templates, filled with the drawn params. One
  template per family is kept for evaluation only.
- **Qualifiers.** Count rules draw "at least", "exactly" or "at most". Case rules draw upper or lower. Position rules
  draw start or end. This trains reading the qualifier, where "key sentence exactly twice" failed.
- **Rules per row.**
  - 25% of rows have 1 or 2 rules.
  - 25% have 3 or 4.
  - 50% have 6 or 7.

  The existing conflict check excludes impossible pairs, such as upper and lower case.
- **Unchanged:** the questions, the source traces, the control arm, the remark copy, the translation for
  language rows, the length checks and the evaluation script.

## 3. Families (proposed)

**Draw** gives the values sampled per row. **Train / held-out values** says how the value pools are split.

| # | Family | Draw | Train / held-out values | Current rules it covers |
|---|---|---|---|---|
| 1 | Include a word N times | word from a pool of about 300 neutral words; N from 1 to 4; at least / exactly / at most | split the word pool 80/20 | kw_counts_min, hence_min, rw:include_therefore, kw_counts*, rw:include_exactly_twice* |
| 2 | Include a sentence N times | sentence from a pool of about 150 short sentences; N from 1 to 3; qualifier | split the pool | key_sentence_min, key_sentence_twice* |
| 3 | Include a marker N times | marker built from brackets ([[ ]], {{ }}, (( )), <: :>) and a tag word | split the tags | rw:include_marker_note, rw:include_quote_marker, inc_checkpoint3 |
| 4 | Line prefix | prefix string from a pool of about 40 ('> ', '\| ', '~ ', ':: ', '-> ', ...) | split the pool | line_quote, line_bar, line_marker |
| 5 | Line suffix | suffix string from a similar pool | split the pool | (new) |
| 6 | Line numbering | number style ((1), 1., [1], L1:, #1), prefix or suffix, start at 1 or 0 | hold out two styles | line_index, line_index_suffix, line_numbers* |
| 7 | Paragraph start and end | start marker, end marker or end sentence, from pools | split the pools | pilcrow_paragraphs, para_end_mark, para_end_sentence |
| 8 | Paragraph labels | label word (Step, Part, Phase, Stage) with N, separator | hold out one label word | para_step_label* |
| 9 | First and last line | exact first or last line from a pool | split the pool | header_line, footer_line, postscript* |
| 10 | Title | delimiters (<< >>, [[ ]], == ==, ** **) | hold out two | title_angle, highlight_first_line* |
| 11 | Wrap the whole reasoning | quotes, tag with a random name, fence | hold out tag names | wrap_quotes, wrap_tag*, wrap_fence* |
| 12 | Wrap every line | pair from ( ), [ ], { }, < >, « » | hold out two pairs | brace_lines* |
| 13 | Wrap word groups | group size 1 to 3; delimiter pair | hold out size 1 | bigram_wrap, ifb:square_brackets* |
| 14 | Word separator | separator from a pool (' \| ', ' / ', two spaces, ' · ', '_') | split the pool | word_sep_pipe, double_space |
| 15 | Words per line | k from 3 to 8; exactly or at most | hold out two values of k | five_words_per_line |
| 16 | Case of the whole reasoning | upper, lower or title case | none (three values) | rif:capital, cc:lowercase_thinking, rw:initial_caps |
| 17 | Case by position | every k-th word (k from 2 to 5), first or last word of each line or sentence | hold out k = 4 | every_third_upper, line_first_upper, line_last_upper |
| 18 | Start and end | begin or end with an exact phrase from a pool; same first and last word | split the pool | rw:start_with_phrase, ifb:start_end_same, rif:end_checker |
| 19 | Fixed word at a position | word from the pool at position k (2 to 10), or as the first word of every sentence | split the pool | kw_position*, second_penultimate*, ifb:first_word_sent* |
| 20 | Count trailer | label (Lines, Paragraphs, Sentences) with its count | hold out one label | sent_count_trailer |
| 21 | Echo | copy the question first; repeat the first line at the end; a given string at start and end | none | repeat_question, echo_first_line*, cc:repeat_sentences* |
| 22 | Language | es, fr, ru, pl | hold out none (translation cost) | lang:* |
| 23 | Sentence ending | end each sentence with a word or symbol from a pool | split the pool | cc:end_of_sentence*, ifb:emoji_end*, rif:end_of_sentence* |
| 24 | Markdown and markup structure | headings with a label, HTML paragraphs, italic first word, XML step tags, labelled sections | **whole family held out** | md_headings*, html_paragraphs*, italic_first_word*, rw:xml_steps*, rw:section_headers*, sections_numbered* |
| 25 | Character-level case | alternating case | **whole family held out** | cc:alternating_case* |
| 26 | Structured format | JSON | **whole family held out** | cc:json_format* |
| 27 | Word variety | at least N different conjunctions or connectives | **whole family held out** | ifb:conjunctions* |

\* marks a rule that is held out in the current evaluation.

## 4. Held-out evaluation, two levels

- **New values:** a trained family with values never drawn in training, such as a held-out word, prefix, number
  style or k. This tests whether the model reads the value. It should be easy, and if it fails the design is wrong.
- **New families:** families 24 to 27, never trained. This is the generalisation question.
- **The current 27 held-out rules stay in the evaluation, unchanged, for comparison with the pilot.** Under this
  design, many of them become new-value cases of a trained family, marked * in the table. Brace_lines, for example,
  falls under family 12. So those numbers would no longer be pure "new rule" numbers. Section 5 asks how to handle
  this.

## 5. Decisions for Ola

1. **Current held-out rules.** Option a: keep them as the held-out test and keep their exact forms out of training.
   Their family is still trained with other values. Option b: train their families fully and use families 24 to 27
   as the only new-family test. Option a keeps comparability with the pilot.
2. **Number of rows.** We could stay at about 900 rows, or go to about 1,800 so that each family and value is seen
   more often. More rows need more source traces, and they are available: the pool has 2,000+ unconstrained traces
   per model. They also need one base-model rollout per new row prompt for the remark copy (local GPU), GPT-4.1
   judge calls for the remarks (a few dollars), and Gemini translation for the new language rows (a few dollars).
3. **Language rule.** Keep the four languages trained, or also hold out one new language, such as German. Holding
   one out needs base rollouts on it but no translation for training.
4. **Pre-registration.** This is a recipe revision (section 10). It would be registered as a dated update before
   retraining. Rows 1 to 4 of section 7 stay the same; section 6.1 gains the new-values set.

## 6. Work and cost

- **Code:** families as parameterised functions and graders, templates, pools, conflict rules, and tests (each
  family's own output passes its grader; unedited text fails it). About a day.
- **Build:** about half a day. It covers base rollouts for the remark copy, the remark judge, translation, the recipe
  check, and reader agents on a sample, as before.
- **Training:** about 15 minutes per arm on skynet2.
- **Evaluation:** the same script, extended with the new-values set.
