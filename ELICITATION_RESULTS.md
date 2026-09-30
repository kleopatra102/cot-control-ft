# Eliciting CoT controllability: results so far

*Interim write-up, 2026-09-30 evening. Design: `ELICITATION_PLAN.md`. Base Qwen3-8B is complete for E0–E7;
Q5 and U are still running. Test set: 160 prompts per strategy (six single constraints × 20,
four triples × 10) on held-out ReasonIF questions; sampling at temperature 1. "All met" = every constraint in the prompt
satisfied. "Effective" = all met, correct answer, no narration of the rules, not truncated. Accuracy is on the same
prompts.*

## Base Qwen3-8B, complete

| strategy | all met | single rule | triples | graded score | accuracy | narrates | effective |
|---|---:|---:|---:|---:|---:|---:|---:|
| E0 plain | 8.1 % | 10.8 % | 0 % | 0.30 | 65 % | 9 % | 6.9 % |
| E1 Redwood-style wording | 7.5 % | 10.0 % | 0 % | 0.31 | 63 % | 11 % | 5.6 % |
| E2 monitoring and evaluation awareness | 8.8 % | 11.7 % | 0 % | 0.29 | 61 % | 8 % | 7.5 % |
| E3 one worked example | 16.2 % | 21.7 % | 0 % | 0.34 | **47 %** | 8 % | 8.1 % |
| E4 best of 3 samples | 13.1 % | — | — | 0.35 | 67 % | 8 % | 10.0 % |
| E5 prefilled compliant opening | **32.5 %** | **30.8 %** | **37.5 %** | **0.60** | 62 % | 5 % | **23.1 %** |
| E6 gpt-5-optimised instruction | 11.2 % | 15.0 % | 0 % | 0.31 | 66 % | 5 % | 8.8 % |
| E7 rules repeated 15 times | 9.4 % | — | — | 0.28 | 63 % | 11 % | 6.2 % |

Admissibility rule (accuracy no more than 10 points below E0's 65 %): **E3 fails** it (−18 points); every other
strategy passes.

Per constraint, single-rule prompts only (20 each, so differences under about 25 points are noise):

| strategy | language | word budget | capitals | end phrase | no comma | end-of-sentence word |
|---|---:|---:|---:|---:|---:|---:|
| E0 | 22 | 33 | 0 | 6 | 12 | 0 |
| E1 | 22 | 39 | 0 | 6 | 0 | 0 |
| E2 | 24 | 41 | 0 | 6 | 13 | 0 |
| E3 | 22 | 50 | 0 | 33 | 41 | 0 |
| E5 | **100** | 50 | **31** | 0 | 18 | 6 |
| E6 | 24 | 61 | 0 | 0 | 18 | 0 |

## What the base results say

1. **Rewording the request does nothing.** E1 (check each sentence, don't mention the rules), E2 (a monitor is
   watching, you are being evaluated), E7 (the rules repeated fifteen times) and E6 (six gpt-5-written instructions, the best chosen on held-out tuning
   questions) all land within 3 points of the plain prompt. The optimiser's six candidates scored 11–14 % on the tuning
   prompts against 11 % plain; nothing it wrote moved the model. That matches Chen et al., who report at most about
   4 points from similar framing.
2. **Prefilling a compliant opening quadruples compliance at no accuracy cost.** E5 starts the reasoning with one
   sentence already in the required form (in the right language, upper-cased, comma-free, ending in the required
   word). All-met compliance goes from 8 % to 33 %, and on three-rule prompts from 0 % to 38 %, while accuracy stays at
   62 %. Language becomes perfect (22 → 100 %) and capitals appear for the first time (0 → 31 %): once the model has
   started in the format, it often keeps going. It does nothing for the end phrase, which is a rule about the end of
   the trace, not its start.
3. **A worked example helps but costs too much accuracy.** One example doubles compliance (8 → 16 %), mainly on the
   end phrase (6 → 33 %) and commas (12 → 41 %), but accuracy falls from 65 % to 47 %. By the rule we set, that is
   over-elicitation.
4. **Sampling more helps a little.** The best of three plain samples reaches 13 % against 8 % for one, with accuracy
   unchanged.
5. **Three-rule prompts are at zero for every strategy except prefill.** Only E5 gets base to satisfy three rules at
   once, and it does so as well as it satisfies one.

So base Qwen3-8B has considerably more controllability than a plain request shows (at least 33 % against 8 %), but
reaching it takes putting the first words in its mouth, not better instructions.

## Q5 (fine-tuned, five constraints per example), complete

| strategy | all met | single rule | triples | graded score | accuracy | narrates | effective |
|---|---:|---:|---:|---:|---:|---:|---:|
| E0 plain | 48.1 % | 47.5 % | 50.0 % | 0.69 | 58 % | — | 30.6 % |
| E1 Redwood-style wording | 41.9 % | 43.3 % | 37.5 % | 0.66 | 55 % | 8 % | 28.1 % |
| E2 monitoring and evaluation awareness | 46.9 % | 45.8 % | 50.0 % | 0.70 | 63 % | 5 % | 31.9 % |
| E3 one worked example | 47.5 % | 49.2 % | 42.5 % | 0.71 | **45 %** | 6 % | 24.4 % |
| E4 best of 3 samples | **57.5 %** | — | — | **0.79** | 61 % | — | **35.6 %** |
| E5 prefilled compliant opening | 41.9 % | 44.2 % | 35.0 % | 0.70 | 56 % | 7 % | 26.9 % |
| E7 rules repeated 15 times | 40.6 % | 40.0 % | 42.5 % | 0.65 | 53 % | 4 % | 25.6 % |
| E6 gpt-5-optimised instruction | **57.5 %** | — | — | **0.78** | 56 % | 5 % | **36.2 %** |

**For Q5 no hand-written prompting strategy adds anything; the per-model optimised one does.** The fine-tuned model already satisfies 48 % of prompts plainly,
six times base, and every rewording, the worked example and even prefill land within noise of that or slightly
below (n = 160, so differences under about 10 points are not reliable). Only sampling more (best of three: 58 %) and the optimised instruction (E6: 58 %, accuracy 56 %) help. For Q5 the
optimiser found a real gain on the tuning prompts (31 → 56 %, with accuracy 56 → 47 %, inside the 10-point rule), and it
held on the test prompts (48 → 58 %); for base the same budget found nothing. The winning Q5 instruction tells the
model to parse the rules first and apply them to the reasoning only. Prefill, the one strategy that transformed base, does nothing for Q5: the model already starts in format.
The worked example again costs about 13 points of accuracy. Fine-tuning has captured what elicitation could extract
and more: prefill lifts base to 33 %, still well short of Q5's plain 48 %.

## Partial results (not yet complete; biased toward the first constraints in the run order)

- **E7, rules repeated 15 times, base (now complete):** 9.4 % all met, 63 % accuracy, effective 6.2 %: no better than
  the plain prompt. The early partial number (27 %) came from the first, easiest constraints in the run order.
- **U (unlearned):** not started.

## Still to come

U through all strategies, and the headline comparison: whether prefill and the other strategies
bring U back to Q5's level (the unlearning suppresses the behaviour) or not (the unlearning survives elicitation).
Estimated about four more GPU hours.
