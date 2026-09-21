# Steering plan: meta-discussion and controllability directions on Qwen3.5-9B

Status 2026-09-21: pieces 1–5 built and tested end to end on CPU (`scripts/steer/cpu_test.py`, Qwen3-0.6B
stand-in). No GPU work yet. The GPU is shared with a colleague's `llama-server` (28 GB, idle-unloads after
10 min); coordinate before a multi-hour run.

## Questions

1. Is there a linear **meta-discussion direction** in the residual stream, and does it generalise across
   constraints (held-out modes) and benchmarks (CoTControl → ReasonIF)?
2. Steering **against** it during generation: does narration fall (LLM lister), and does compliance
   (a) stay flat — narration is a symptom — or (b) fall — narration is how the model tracks the constraint?
   The strip test (`STRIP_TEST.md`, `META_DISCUSSION_FULLTRACE.md`) already rules out the direct route; this is
   the indirect one.
3. Is there a **controllability direction** distinct from per-condition **style** directions, and does it
   transfer across conditions?

## Data and directions

| direction | positives | negatives | matching | source |
|---|---|---|---|---|
| meta-discussion | LLM-labelled narration sentences (full trace) | non-narration sentences from the same trace, nearest position, regex-ambiguous excluded | same trace ⇒ same compliance; position-matched | `results/strip_llm/rollouts_base_*.jsonl` (step-60 when its labels land) |
| style (per condition) | transformed compliant trace, no instruction (D) | original trace, no instruction (C) | same question, same text modulo the transform | uppercase / lowercase / alternating (CoTControl), english_capital / no_comma (ReasonIF) |
| controllability | (B − A) − (D − C) | | instruction present in A/B, absent in C/D | same quartets |
| natural validation | ReasonIF compliant rollouts (≈17 base, ≈70 step-60) | non-compliant, same type | none | stored rollouts |

Sizes: ~2,000 narration + 2,000 matched negatives from ~500 traces (cap 6 per trace) for fitting; 20 % of
questions held out; leave-one-mode-out; all ReasonIF as transfer set. Quartets: up to 200 per CoTControl
condition, 40–55 per ReasonIF condition (all available).

Vectors are read in context: one forward pass over chat template + `<think>` + trace, activations pooled over
the sentence's tokens (mean and last-token both kept). Direction = plain contrastive mean difference,
unit-normalised. Probe check (read-only, no steering): AUROC of the projection on held-out sentences vs a
random direction vs a logistic-regression ceiling. Steer only if held-out-mode AUROC is clearly above chance
and transfer to ReasonIF holds.

## Model geometry and layers

32 decoder layers, hidden 4096. Sweep layers 8, 12, 16, 20, 24 in one extraction pass (hooks on all five).
Base checkpoint is the multimodal wrapper (`Qwen3_5ForConditionalGeneration`); merged step-60 is
`Qwen3_5ForCausalLM`; `activations.decoder_layers()` resolves both.

## Steering runs

Sampling identical to the eval: temperature 1.0, top_p 0.95, top_k 20, user message only. Token cap 8,192
(truncation tracked). Coefficients reported relative to the mean activation norm at the layer.

| stage | what | prompts | GPU time (est.) |
|---|---|---|---|
| E1 | extract span activations, base, CoTControl + ReasonIF, 5 layers | ~700 traces | 15 min |
| E2 | extract quartet activations, base | ~800 quartets × 4 | 60 min |
| F | fit directions, probe tables | — | minutes, CPU |
| S1 | steer base against meta-discussion at best layer, coefs {−c, 0, +c}, 2 conditions × 40 prompts | 240 rollouts | 2–3 h |
| S2 | if S1 informative: all 9 CoTControl modes × 30 prompts × 3 coefs | 810 rollouts | 6–8 h |
| S3 | style/controllability steering on 2 held-out conditions | ~240 rollouts | 2–3 h |
| repeat E1/F/S1 on step-60 | | | +4 h |

Evaluation of steered rollouts: existing binary graders, continuous v2 scores, accuracy, truncation, and the
full-trace LLM lister (`judge.narration_sentences`) for narration rate — ~$0.006 per rollout.

## Predictions, written before running

- Meta-discussion direction: held-out-question AUROC > 0.85 at mid layers; held-out-mode lower but > 0.7;
  transfer to ReasonIF > 0.7 if the direction is about constraint narration rather than the "do not mention"
  clause (which ReasonIF prompts lack).
- Negative steering lowers narration rate by ≥ 20 pp at a coefficient that leaves accuracy within 5 pp.
- Compliance under negative steering: prior from the fine-tuning result (narration −31…−50 pp, compliance
  +0.8 pp) is (a) flat. If continuous scores fall by > 0.03 on average, that supports (b).
- Style directions: high-norm, near-perfect probe, transfer *within* case conditions (upper/lower/alternating
  share a case axis?) but not to suppression modes. Controllability residual: small norm; the test is whether
  it has any held-out AUROC at all.

## Code map

| piece | module | CLI |
|---|---|---|
| 1 spans → token spans, matched negatives | `src/cotctl/steer/spans.py` | `scripts/steer/build_spans.py` |
| 2 controllability quartets | `src/cotctl/steer/pairs.py` | `scripts/steer/build_pairs.py` |
| 3 activations (hooks, pooling) | `src/cotctl/steer/activations.py` | `scripts/steer/extract.py` |
| 4 directions, AUROC, probe, deconfound | `src/cotctl/steer/directions.py` | `scripts/steer/fit_directions.py` |
| 5 steered generation | `src/cotctl/steer/harness.py` | `scripts/steer/steer_generate.py` |
| test | | `scripts/steer/cpu_test.py` |

Outputs land in `results/steer/` (gitignored except summaries); directions and probe tables are small and
will be committed.

## Known limitations to carry into the write-up

- Mean-difference directions absorb any correlate of the label; position is matched, keyword mention in
  suppression modes is not (checked via held-out-mode AUROC).
- Quartet texts B/D are teacher-forced transforms the model did not write; activations on them are
  somewhat off-distribution.
- Adding a constant vector at every position is the simplest intervention; it can degrade fluency at high
  coefficients, hence the accuracy and truncation checks.
- HF generation with hooks is slow (~20 tok/s per sequence); sample sizes are set by that, not by choice.
