# Unlearning controllability: does training on non-compliant reasoning generalise?

*Phase 2 of the Qwen3-8B multi-constraint experiment. Phase 1 (`QWEN3_8B_PLAN.md`, `QWEN3_8B_FINDINGS.md`)
trained Q5 on five ReasonIF-derived constraints per example and found 12 % binary transfer to CoTControl,
concentrated in JSON, lowercase, uppercase and end-of-sentence.*

## Question

If a model that has learned to control its reasoning is then fine-tuned on reasoning that ignores the
constraint in its prompt, does the loss of control stay on the constraints it was trained to ignore, or does
it generalise to constraints and tasks never seen in either phase? The mirror of phase 1's transfer
question: is controllability one shared skill or a bundle of per-format skills.

## Starting model

Q5-final (Qwen3-8B + phase-1 LoRA, merged into the weights). Headroom: ReasonIF singles 42 %, CoTControl
singles 12 % joint, json_format 55 %, lowercase 25 %, uppercase 18 %, end_of_sentence 18 %.

## Three benchmarks, three roles

| role | constraints | prompt template |
|---|---|---|
| phase-1 learning (done) | 6 ReasonIF-derived: reasoning_language, number_words, capital, end_checker, no_comma, end_of_sentence | ReasonIF "rules" template |
| phase-2 unlearning | 8 CoTControl modes: uppercase_thinking, alternating_case, word_suppression, multiple_word_suppression, repeat_sentences, end_of_sentence, meow_between_words, ignore_question | CoTControl "Requirement: … do not mention" template |
| held out within CoTControl | json_format, lowercase_thinking (the two with most headroom; JSON is the most novel transferred format) | CoTControl template |
| never seen in either phase | ~10 IFBench-derived reasoning constraints (`UNLEARNING_CANDIDATE_CONSTRAINTS.md`), frozen after calibration | both templates |

## Data for the unlearning phase

1. Questions: the CoTControl pool minus the 300 evaluation questions, ~900 questions (HLE, GPQA, MMLU-Pro).
   No overlap with the evaluation draw.
2. Traces: Q5-final answers each question with the plain question prompt (no Requirement line), thinking on.
   On-policy, so the traces are what Q5 writes anyway; no editing.
3. Prompts: one of the eight unlearning modes per question, uniform, rendered with the exact CoTControl
   template including the no-mention clause and the mode's control value (keyword etc.).
4. Verification: every (prompt, trace) pair graded with the CoTControl grader; pairs that pass by accident
   are dropped. Expected ~900 examples.
5. Control arm data: the same traces under the plain question prompt.

## Arms

| arm | prompt | trace | examples | checkpoints |
|---|---|---|---|---|
| Q5 | — | — | — | reference, already evaluated |
| U (unlearning) | question + CoTControl requirement | Q5's unconstrained trace | ~900 | step-15 (60 ex.), step-60 (240), step-final |
| C (matched control) | plain question | same trace | same | same |

Same LoRA recipe as phase 1 (r 32, α 32, lr 1e-4, one epoch), trained on top of the merged Q5 weights.
The estimand is U minus C at each dose.

## Four evaluations, on Q5, U and C

1. **Trained-away modes** (8 CoTControl modes, 300 evaluation questions, 40 per mode): should fall to base.
2. **Held-out CoTControl modes** json_format and lowercase_thinking, same questions: the within-template
   generalisation test.
3. **Never-seen constraints** (frozen IFBench set): on ReasonIF questions (unseen tasks) and on the 300
   CoTControl evaluation questions, in both the ReasonIF and the CoTControl template, 20 prompts each.
4. **Backward**: the six phase-1 ReasonIF constraints, k = 1, 20 prompts each: does unlearning CoTControl
   modes undo what phase 1 taught.

Plus accuracy and answer-tag formatting on every suite, and continuous scores everywhere (a rule can move
far before the all-or-nothing verdict changes). Meta-discussion is not measured.

## Calibration before freezing the never-seen set

The candidates have never been in any prompt to Q5, so their compliance may be at floor. Run 20 prompts
per candidate on Q5-final and on base (about 400 rollouts), keep candidates with measurable binary
compliance (roughly ≥ 10–15 %) or a clearly non-floor continuous score, and freeze the set before any
unlearning training. Candidates, by granularity: newline_words, square_brackets, stop_words (whole trace);
emoji_end, first_word_sent, sentence_type_ratio (per sentence); no_consecutive_initial (per token);
conjunctions, start_end_same, repeats (counting / boundary).

## Cost

| step | GPU |
|---|---:|
| Q5 traces on ~900 questions | ~1 h |
| calibration of candidates (Q5 and base) | ~0.5 h |
| merge Q5, train U and C | ~0.5 h |
| six checkpoints × combined suite (~920 requests: 400 CoTControl singles, ~400 never-seen, 120 ReasonIF) | ~12 h |

## Predictions

1. U drops the eight trained-away modes to base level at every dose; C does not.
2. If controllability is shared: json, lowercase, the never-seen constraints and the phase-1 ReasonIF
   constraints fall under U more than under C, with whole-trace formats falling most and per-token rules
   least, mirroring the phase-1 transfer pattern.
3. A small dose (60 examples) already produces most of the generalised drop.
4. C stays within noise of Q5 at every dose, because its traces are Q5's own.
5. Accuracy is unchanged; answer-tag formatting survives.

## Status

Not started. Order: traces → calibration (needs the ten new graders) → build datasets → merge and train →
evaluate U-final and C-final first, then the small doses.
