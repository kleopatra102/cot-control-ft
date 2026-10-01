# Many-rule SFT on Qwen3.8-27B: plan

*2026-10-01.* Does training on many more kinds of reasoning rule widen transfer to rules never trained? The current
Q5 model saw 6 rules; the new arms see about 32, 7 per training example. There are two arms, and each holds out a
different set of conditions:

- **A, split by family.** Whole families are trained or tested.
- **B, split within family.** Every family that has more than one operation appears on both sides, split by
  operation.

Everything else is unchanged: Qwen3.8-27B, QLoRA on the 4-bit base, one epoch, about 460 examples from the same 480
stage-1 traces, and evaluation on Red Hat's INT4 weights with single-rule prompts and identical prompts across base,
Q5, A and B.

## Grouping

- **Operation.** Two conditions are the same operation if they differ only in a parameter (which word, which number,
  which language), or if satisfying one satisfies the other. An operation is never split between training and
  testing.
- **Family.** A broader theme that groups operations. A splits whole families; B splits a family only between
  different operations.

| family | operation | conditions (source) |
|---|---|---|
| Case | uniform case | all caps (ReasonIF `capital`, CC uppercase, RW all_caps), lowercase (CC, RW all_lower), initial capitals (RW) |
| | per-letter pattern | alternating case (CC) |
| Bans | word ban | word suppression, multiple-word suppression (CC), no "the", no "answer", no "so" (RW) |
| | character ban | no commas (ReasonIF, RW) |
| Inclusion | specific word or marker | "therefore", [[NOTE]], >>>, "hence" exactly twice (RW) |
| | word class | at least 6 coordinating conjunctions (IFBench) |
| Position | whole trace | end phrase (ReasonIF), start with phrase (RW), repeat sentence (CC), start = end word (IFBench) |
| | every sentence | end-of-sentence word (ReasonIF, CC), emoji at end, "Indeed" first (IFBench) |
| Word layout | separator | meow between words (CC), one word per line (IFBench) |
| | wrapping | square brackets around every word (IFBench) |
| Structure | line-prefix lists | bullets, numbered (RW) |
| | markup | XML steps (RW), JSON (CC) |
| | labelled sections | section headers (RW) |
| Style | voice | second person (RW) |
| | sentence mood | write as questions (RW), 2:1 statements to questions (IFBench) |
| | register | child explanation (RW) |
| Statistics | word frequency | no word > 10 times, stop words ≤ 35 % (IFBench) |
| | letter adjacency | no two consecutive words sharing a first letter (IFBench) |
| Length | word cap | word budget (ReasonIF), 25/50/30–60/70-word caps (RW) |
| Language | language | five languages (ReasonIF), reason in Spanish (RW) |

These are left out: ignore question (needs the judge), and no first person (second-person writing mostly satisfies
it, so it straddles two operations).

## The two splits

| | A: train | A: test | B: train | B: test |
|---|---|---|---|---|
| Case | all | | uniform case | alternating case |
| Bans | all | | no commas | word bans |
| Inclusion | all | | specific words and markers | conjunctions |
| Position | all | | whole trace | every sentence |
| Word layout | | all | brackets | meow, one word per line |
| Structure | | all | markup, section headers | bullets, numbered |
| Style | | all | voice, sentence mood | child explanation |
| Statistics | | all | word frequency | letter adjacency |
| Length | all | | all | |
| Language | all | | all | |

That gives A 34 training and 15 test conditions, and B 32 training and 17 test conditions. B's test side counts the ReasonIF and CoTControl end-of-sentence word separately.

The **shared core** is held out in both arms and gives the direct A-against-B comparison: meow, one word per line,
bullets, numbered, child explanation and letter adjacency.

## Building the training data

Each example takes one stage-1 trace and 7 conditions. The trace is turned into a compliant one in a fixed order:

1. **Content rewrite.** A single editor call (gpt-4.1-mini, T = 0) handles every content condition at once, together with
   the length target when one is drawn, so a separate condense step cannot undo the content edits:
   - second person, questions, the 2:1 ratio;
   - word bans;
   - conjunctions;
   - stop words and word frequency.

   It is skipped when the example has none of these.
2. **Translation**, if a non-English language is drawn. This is the existing METR prompt.
3. **Condense** to the length target, using the existing prompt and leaving headroom for words added later.
4. **Deterministic edits**, done in code, in this order:
   1. inclusions;
   2. per-sentence edits;
   3. no commas;
   4. word wrapping;
   5. structure;
   6. whole-trace position;
   7. case. Protected literals such as [[NOTE]] and the end phrase are left untouched.
5. **Verify** every condition with the grader used at evaluation. The LLM-judged style conditions (second person,
   questions) are checked by gpt-4.1 at T = 0; in the pilot gpt-4.1-mini rejected clearly compliant traces. The same
   judge scores those two instructions at evaluation. An example is kept only if all 7 pass. A failed draw is redrawn
   on the same trace, up to 3 attempts.

**Sampling rules for the 7 conditions:**
- compatible conditions of the same operation may share an example (two word bans, two markers), but never two
  wordings of the same rule (no commas from two sources) or contradictory ones (questions with the 2:1 ratio);
- at most one case operation;
- at most one position condition;
- at most one structure or word-layout condition;
- no English-word rules together with a non-English language;
- a conflict list of known incompatible pairs: brackets with exact strings, JSON or XML with whole-trace position,
  conjunctions with no "so", lowercase or alternating case with fixed upper-case strings, and so on.

Within those rules, conditions are drawn greedily towards balanced coverage. A quarter of examples are language rows,
which start from a language condition (80 % non-English), so that "reason in English" is not used as a filler.

**As built.** A 40-example pilot per arm shaped the conflict list.
- A: 456 examples, all with 7 conditions.
- B: 427 examples, all with 7 conditions.
- Coverage per training condition ranges from 50 to 158 examples in A and 36 to 183 in B. The family caps make case,
  position and language rarer than bans and inclusions.
- Data: `data/sft/q38many_{A,B}.jsonl`; per-condition stats are in `results/qwen38_many/build/`.

The training prompt is the ReasonIF multi-rule template, with each condition in its source's own wording.

## Evaluation

All four models (base, Q5, A, B) run the same suites:
- ReasonIF singles (6 × 20);
- CoTControl singles (10 × 20);
- IFBench singles (10 × 20);
- Redwood, on its nine held-out instructions plus four more (second person, questions, no "the", no "answer"),
  29 tasks each.

Base and Q5 run only the four new Redwood instructions; their other numbers are reused. Each condition is labelled
trained or held-out per arm.

**Headline numbers:** held-out micro and macro per arm against base and Q5, on that arm's own test set and on the
shared core. Conditions where base is already high (section headers, stop words, conjunctions) are reported
separately.

## Confounds, stated in advance

- Compared with Q5, two things change at once: the number of rules (6 to about 32) and the number per example (5 to
  7).
- Each condition appears in fewer examples (about 100, against about 380 in Q5).
- Some Redwood instructions are now trained, so a Redwood macro over all nine instructions is no longer quotable.

## Cost

Building the data is about 10 minutes of API time per arm. Training is about 10 minutes per arm. Evaluation is about
1 hour per arm, plus about 15 minutes for base and Q5. That is roughly 3 GPU hours in total, under
`gpu_supervisor`.
