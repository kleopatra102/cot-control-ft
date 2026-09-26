# Multi-constraint SFT on Qwen3-8B, one to five constraints per example

*Status 2026-09-26: run complete; results in `QWEN3_8B_RESULTS.md`, findings in `QWEN3_8B_FINDINGS.md`. Originally a draft for discussion. The Qwen3.5-9B experiment (`MULTI_CONSTRAINT_PLAN.md`,
`CONSTRAINT_MIX.md`, `CONSTRAINT_PAIRING.md`, `MULTI_CONSTRAINT_FINDINGS.md`) is the template; this
document lists only what differs.*

## Question

On a second model, does the monotone gain in k (T3 > P2 > S1 on Qwen3.5-9B, at every evaluation level
including unseen combinations) continue when examples carry four or five constraints, or does it saturate
or reverse? And does transfer to CoTControl-style prompts change when those prompts carry up to six modes?

## Constraint set

The agreed six, unchanged: `reasoning_language` (en/es/fr/ru/pl in training; zh/hi/ar in eval singles),
`number_words`, `capital`, `end_checker`, `no_comma`, `end_of_sentence`, with the one forbidden pair
`end_checker` + `end_of_sentence`. Valid combinations: 6 singles, 14 pairs, 16 triples, 9 quads, 2 quints,
no sextuple (every six-set contains the forbidden pair). Training therefore stops at k = 5.

## Model

`Qwen/Qwen3-8B` (dense, 36 layers, hidden 4096, GQA with 8 KV heads, thinking via `<think>` tags).

| item | Qwen3.5-9B (done) | Qwen3-8B (this plan) |
|---|---|---|
| architecture | hybrid linear/full attention, needs `flash-linear-attention` | dense, standard vLLM and PEFT paths |
| chat template | opens `<think>` for the assistant turn | `enable_thinking` flag; tag handling checked on the first rollout |
| KV cache per token | small (8 full-attention layers) | ~147 KB, roughly 3–4× larger → fewer concurrent requests |
| LoRA targets | 248 linear modules | q/k/v/o/gate/up/down × 36 = 252, same r 32, α 32, lr 1e-4 |
| word limits for `number_words` | `data/word_limits_Qwen3.5-9B.json` | recalibrated on Qwen3-8B base traces |
| SFT source traces | `results/sft/stage1_rollouts.jsonl` (937 questions) | regenerated on the same 937 questions with base Qwen3-8B |

Graders, editor (gpt-4.1-mini, temperature 0), compose order, verification, request builder and report are
reused; only the k range and the CoTControl combination sampler change.

## Arms

| arm | constraints per example | training combinations (after hold-out) |
|---|---:|---:|
| S1 | 1 | 6 |
| P2 | 2 | 10 of 14 |
| T3 | 3 | 12 of 16 |
| Q4 | 4 | 6 of 9 |
| Q5 | 5 | 2 of 2 |
| M5 | 1–5, uniform over k | union of the above (named M5 in code/results to keep it apart from Qwen3.5's M = 1–3) |

~915 accepted examples per arm, one epoch (~230 steps at bs 1 × ga 4), checkpoints at step-60 and
step-final. Hold-out (seed 7): the same 4 pairs and 4 triples as before, plus 3 quads; nothing at k = 5.
Q5 trains on two combinations that share four of five constraints, so its generalisation is judged on the
lower levels, which are all unseen as prompts. Editor pass rate will fall with k; budget 2× the retries
for Q4 and Q5.

## Evaluation (final design, ~25 GPU h)

Evaluation, not training, is the cost, so the design drops arms and checkpoints rather than prompts.
Four checkpoints get the full suite, two more get the k = 1 level only:

| checkpoint | suite |
|---|---|
| base, S1 step-final, T3 step-final, Q5 step-final | full: ReasonIF k = 1, 3, 5 and CoTControl k = 1, 3, 6 |
| S1 step-60, T3 step-60 | k = 1 only, both suites (to test whether S1 saturates early and T3 keeps rising, as on Qwen3.5) |

P2, Q4 and M are trained (cheap) but not evaluated in this round; their checkpoints are kept for a later
round if the GPU is free.

**Full suite per checkpoint (~1,110 requests):**

| suite | level | conditions | prompts each | requests |
|---|---|---:|---:|---:|
| ReasonIF | k = 1 | 6 (languages spread inside `reasoning_language`, incl. zh/hi/ar) | 20 | 120 |
| ReasonIF | k = 3 | 16 (4 held out) | 10 | 160 |
| ReasonIF | k = 5 | 2 | 20 | 40 |
| CoTControl | k = 1 | 10 (all) | 40 | 400 |
| CoTControl | k = 3 | 20 of 58, stratified so every mode appears ≥ 3 times (a different set from Qwen3.5's 6 hand-picked triples; k = 1 is identical) | 15 | 300 |
| CoTControl | k = 6 | 3 (all: a case mode + word suppression + multiple word suppression + end of sentence + meow + ignore question) | 20 | 60 |
| CoTControl | unconstrained | — | 30 | 30 |

**k = 1 suite for the step-60 checkpoints (~520 requests):** the ReasonIF k = 1 and CoTControl k = 1 rows.

Metrics as before: joint binary per level (seen / held-out), per-constraint binary by k, continuous
macro on CoTControl, accuracy, truncation, the two "excluding uppercase" views. No meta-discussion
measurement. The report restricts nothing this time: the constraint set is identical to Qwen3.5's, so
S1 and T3 rows compare directly with `MULTI_CONSTRAINT_FINDINGS.md`.

## Time

Qwen3.5-9B: ~5 h per 1,790-request checkpoint, KV-cache-bound. Qwen3-8B's dense KV cache is 3–4× larger
per token; the fp8 KV cache (weights stay bf16, only the cached keys/values are 8-bit) is expected to
recover most of that and is tested first.

| item | fp8 KV works | bf16 only |
|---|---:|---:|
| base rollouts for SFT source (937 questions), calibration | ~4 h | ~4 h |
| training, six arms | ~1 h | ~1 h |
| 4 × full suite (1,110 requests) | ~16 h | ~30 h |
| 2 × k = 1 suite (520 requests) | ~4 h | ~7 h |
| **total** | **~25 h** | **~42 h** |

If fp8 fails: cap generation at 24k tokens (long traces hold the cache longest; truncation rises a few
points and is reported) and drop Q5 from this round.

**Order of runs:** base first, as a gate — its CoTControl k = 1 result (~3 h) shows whether Qwen3-8B has
the higher starting floor the prediction rests on. Then Q5, S1, T3 step-final, then the two step-60s.

## Predictions to write down before running

1. Qwen3-8B base has higher binary CoTControl compliance than Qwen3.5-9B base (0 %); with that floor,
   T3 shows binary transfer on CoTControl k = 1 that S1 does not.
2. In-domain, Q5 ≥ T3 > S1 on ReasonIF k = 1 and k = 3; the gain from k flattens rather than reverses.
3. Held-out triples stay within a few points of seen ones for T3 and Q5.
4. S1 gains base → step-60 and little after; T3 keeps gaining to step-final.
5. CoTControl continuous transfer grows with training k and falls with evaluation k.

## Defaults taken (say if any should change)

- Hold-out (seed 7): the same 4 pairs and 4 triples as on Qwen3.5, plus 3 of the 9 quads; nothing at k = 5.
- M is uniform over k = 1 … 5; all six arms ~915 examples, one epoch, LoRA r 32 / α 32 / lr 1e-4.
- Editor gpt-4.1-mini at temperature 0; ~$10 for six arms.
- Generation cap 32k unless fp8 fails.
- The base gate does not stop the run automatically; it is reported and the run continues unless told
  otherwise.
