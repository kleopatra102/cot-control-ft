# gpt-oss-20b multi-constraint SFT: our run against a colleague's (SPAR week 3)

*Ours: `GPTOSS_PLAN.md`, `GPTOSS_FINDINGS.md`. Theirs: "SPAR week 3 summary" (setups V2, V2.1, V3), read from the
PDF export; their numbers are quoted from its text and figures, so figure-read values are approximate (± 0.02).
Both runs fine-tune gpt-oss-20b on the model's own reasoning rewritten to satisfy combinations of formatting rules,
and ask whether compliance improves on rules that were never trained.*

## The short answer

The two runs agree on the main result: **multi-constraint SFT on gpt-oss-20b improves the trained rules and does
not improve rules it never saw, when those rules are asked for on their own.** They also agree that a held-out rule
sitting *next to* a trained rule is a different matter, and that is where the most interesting difference lies:
their V3 finds a large "package" effect for a never-trained rule (language) combined with trained rules, which our
design never tested for a genuinely unseen rule.

## Setups side by side

| | ours | theirs, V2 | theirs, V2.1 | theirs, V3 |
|---|---|---|---|---|
| training questions | 937 (ReasonIF-style pool) | 50 | 50 (same as V2) | METR's ReasonIF dataset |
| examples | ~915 per arm | 994 | 296 | not stated (93 steps) |
| rules per example | S1: 1, T3: 3, Q5: 5; plus a no-rule control R | 1–3 (20 combinations) | 4–5 | 5 |
| trained rules | reasoning_language, number_words, capital, end_checker, no_comma, end_of_sentence | uppercase, bullets, word suppression, no comma, end phrase | same | capitals, bullets, end phrase, no comma, fewer than N words |
| how traces were made | editor LLM (gpt-4.1-mini) for translation / condensation / end-of-sentence, code for the rest; verified by the grader | rewritten by code; format only | same | not stated |
| unseen rules tested | 10 CoTControl modes; 30 IFBench-derived rules, each alone | lowercase, numbered list, language, JSON, alone and mixed with trained rules | 8 CoTControl modes | language (held out), alone and with trained rules; 8 CoTControl modes |
| evaluation size | ~1,950 prompts per checkpoint | 150 new questions × every known/unknown mix = 3,150 | 8 modes × 100 | METR questions not used in training |
| score | binary (all-or-nothing) and continuous | continuous | continuous | continuous / share obeying |
| checkpoints | base, step 60 (T3), final | base, 15–120 | base, 30, 60 | base, 15, 45, 60, final (93) |
| training stack | Unsloth 4-bit, attention-only LoRA r 32, lr 1e-4, one epoch, 4,096-token cap, medium effort | not stated | not stated | not stated |

## Where the results agree

**1. Trained rules go up.** Theirs: known rules 0.44–0.78 → 0.95 (V2, step 120); uppercase and bullets 0.84 → 0.98.
Ours: single-constraint joint compliance 12 → 33–38 %, reasoning_language 15 → 95 %, and the control arm stays at
base. Their rules start much higher at base because their scores are continuous and several of their rules
(uppercase-ish, bullets) are close to what gpt-oss already does; ours start near 0 because we report all-or-nothing.

**2. CoTControl does not move beyond the trained twin.** Theirs (V2.1): uppercase 0.01 → 0.60, "that's
in-distribution"; the other six OOD modes 0.19 → 0.17. Ours: continuous macro over the nine scorable modes 0.28
(base) → 0.33–0.36 for the trained arms, 0.29 for the control; excluding the two modes that restate trained rules,
0.34 → 0.39–0.41 against the control's 0.35. Binary, the best arm is 4.3 % against the control's 1.8 %, carried by
repeat_sentences. Both runs: no general transfer to CoTControl. The one mode each run moves is the one closest to
something it trained (their uppercase ↔ trained uppercase; our repeat_sentences ↔ trained end phrase, a
start/end-of-trace rule).

**3. Held-out rules asked alone stay flat or fall.** Theirs: a single unknown rule stays at about 0.45; lowercase
0.72 → 0.60, language 0.76 → 0.64, JSON 0.53 → 0.40. Ours: the thirty never-seen rules fall from 15.4 % to 8–9 %
pooled, and CoTControl lowercase and JSON do not move. On the fall, the two runs offer different explanations that
are probably both right:

- ours: base gpt-oss restates the rule in two thirds of its traces, the restatement satisfies inclusion-type rules
  (nested quotes, conjunctions, punctuation, palindromes), and trained arms stop restating; among traces that do not
  restate the rule, every checkpoint passes 5.5–7.6 %, base and control included;
- theirs: "the base model already obeyed them better when they came together", i.e. base compliance on held-out
  rules is partly incidental and training on a fixed rule set displaces it.

Both say the drop is not unlearning of a skill; it is loss of accidental compliance.

**4. The exception is always the nearest neighbour of a trained rule.** Theirs: numbered list (held out) rises
0.76 → 0.85 because bullets were trained. Ours: first_word_sent (continuous) and repeat_sentences rise, the mirrors
of the trained end-of-sentence and end-phrase rules; nothing structurally unrelated moves.

**5. Accuracy.** Theirs: base accuracy falls with the number of rules (0.72 → 0.38) because the model stops after the
end phrase or the JSON without answering; after training it holds at about 0.6. Ours: CoTControl accuracy is
unchanged (50–56 %); ReasonIF accuracy is unreadable because we dropped the answer tags. Their finding is a useful
warning for our design: the end-phrase rule invites the model to end the whole response, not only the reasoning.

## Where they differ, and why it matters

**A. The "package" effect: their clearest positive result, and a gap in our design.** V3 finds that a trained rule
asked alone barely improves (0.20 → 0.27) but improves strongly when combined with other trained rules
(0.29 → 0.74), and that **the never-trained rule, language, behaves the same way: alone 0 → 0.04, together with
trained rules 0.27 → 0.71.** Our in-domain data show the first half of this: per-constraint compliance rises with the
number of rules in the prompt for the trained arms (end_checker for T3: 0 % alone, 32 % in triples, 65 % in
quintuples; no_comma for S1: 15 → 20 → 48 %) and not for base or the control. But in our design every unseen rule
was only ever tested **alone**; we never put a never-seen rule inside a prompt with trained rules. In our runs
reasoning_language was trained, so we have no equivalent of their language result. Their finding suggests that what
multi-constraint SFT teaches is "comply with a list of formatting rules", which reaches an unseen rule only when it
arrives in that list form. That is a different and more positive statement than "no transfer", and it is testable on
our checkpoints at no training cost.

**B. Base compliance levels differ a lot.** Their base lowercase is 0.72, ours 0.92 (continuous); their base
repeat_sentences about 0.52, ours 0.28; their multiple word suppression about 0.35, ours 0.28. Likely causes: their
CoTControl prompts are METR's base-run prompts, ours add a "do not mention the constraints" clause and use a
different sample of 40 questions per mode; different continuous scorers (ours has a known denominator issue on the
suppression modes); and our never-seen and CoTControl runs use medium reasoning effort, theirs is not stated. The
comparison should therefore be made on changes from each run's own base, not on levels.

**C. Rule sets overlap only partly.** Both train no comma and an end phrase. They train uppercase, bullets and word
suppression, which are, respectively, a CoTControl mode, a near-twin of a held-out rule (numbered list), and a
CoTControl mode; we train language, word budget and end-of-sentence, which are held out or unrelated in theirs. So
their CoTControl "OOD" set contains two of their trained rules (uppercase, word suppression), and ours contains two of
ours (uppercase ↔ capital, end_of_sentence). Both runs correctly flag these.

**D. Scale of the training set.** They use 50 questions (994 examples at 1–3 rules; 296 at 4–5), we use ~920
questions with one example each. Their data repeat questions heavily; ours repeat rules. That their V2.1 (296
examples, 4–5 rules) behaves like V2 (994 examples, 1–3 rules) matches our finding that five-per-example is not better
than three-per-example on anything but five-rule prompts.

**E. What neither run has.** One seed each; no measurement of meta-discussion on the trained checkpoints (we found it
drives the never-seen numbers); no test of an unseen rule that is structurally far from every trained rule but
presented inside a package. Their V3 language result is the only data point of that kind, and it is one rule.

## What to do next

1. **Package test on our checkpoints (no training, ~1 GPU hour).** For each never-seen rule, evaluate it inside a
   prompt with two or four trained rules, on base, R, S1, T3 and Q5. If never-seen rules rise when they arrive with
   trained ones, as language did in V3, the transfer claim becomes "multi-constraint SFT teaches list compliance",
   and the positive result is ours to replicate rather than theirs alone.
2. **Swap one rule set.** Train our pipeline on their five rules (or theirs on ours) so that one run uses the other's
   held-out set; the numbered-list and repeat-sentences exceptions predict which held-out rules move.
3. **Drop or flag the inclusion rules** (nested quotes, punctuation, conjunctions, palindromes, parentheses) from any
   never-seen set, and report restating and non-restating traces separately.
4. **Align the CoTControl prompt** (with or without the no-mention clause) and the continuous scorer before comparing
   levels across the two runs.
