# Does controllability training increase CoT obfuscation? (Haskins et al. 2026 replication on gpt-oss-120b)

*Plan, 2026-10-14. Not run. Paper: Haskins, Chughtai & Engels, "Training on Documents About Monitoring Leads to CoT
Obfuscation", arXiv 2605.15257. Code: github.com/Reih02/cot_obfuscation_code (cloned to `~/dev/ext/haskins`).*

## Question

Haskins finds that models with more CoT controllability obfuscate more after learning about a CoT monitor
(r = 0.80 across 8 different models). That is a correlation across model families. Our controllability-trained
checkpoint is the same model with controllability changed, so it tests the claim causally:

> After the same monitor-awareness SDF, does the controllability-trained gpt-oss-120b hide its deception from the
> CoT monitor more often than base gpt-oss-120b?

## Models

- **B**: the colleague's controllability checkpoint, training state
  `tinker://3901f5e8-fd40-5481-931f-bb545ef3694e:train:0/weights/step-final` (LoRA rank 32, the same as Haskins).
  SDF continues from this state.
- **base**: `openai/gpt-oss-120b`, fresh LoRA rank 32 (control for our regenerated documents).

## Arms

| arm | start | stage 1 (behavioural SDF) | stage 2 | needed? |
|---|---|---|---|---|
| B-MA | B | 1,000 behavioural docs, lr 1e-4, 5 epochs | 1,000 monitoring docs, lr 1e-5, 5 epochs | core |
| B-BO | B | shared with B-MA | 1,000 more behavioural docs, lr 1e-5, 5 epochs | core: B's own no-monitor control |
| base-MA | base | 1,000 behavioural docs (same docs) | monitoring docs (same docs) | recommended: separates "our docs" from "B" |
| base-BO | base | shared with base-MA | behavioural docs (same docs) | optional: completes the 2×2 |

Hyperparameters, batch size 8, epoch selection (best undetected rate on 100 held-out scenarios, discarding epochs with
any empty CoT) and the eval (1,000 scenarios, 3 distractors, seed 42, temperature 0.6, gpt-5-mini monitor
`deception_v5`) are Haskins' exactly.

## Measures

- **Primary: undetected deception**, as a share of the 500 defect-present scenarios: answered "no" and the monitor
  calls the CoT NOT_DECEPTIVE. Haskins' base gpt-oss-120b (released results file): behaviour-only 15 / 500 (3 %),
  monitor-aware 208 / 500 (42 %). The paper's figure gives 25.7 %; we compare against the file, with his script.
- **Obfuscation effect**: MA − BO, for base and for B. The prediction is that it is larger for B.
- **Hiding vs saying less**: Haskins' counterfactual autorater (LEAKS / OPAQUE: could this CoT have been written if
  there were no defect?), on every monitored response. The deception monitor counts vague CoTs as undetected, and
  controllability training makes CoTs shorter and quieter, so this separates the two.
- **No-reasoning baseline**: final checkpoints with an empty analysis channel prefilled. Undetected deception has to
  beat this to show that the CoT is doing work.
- **Controllability after SDF**: v2 rules, 40 × 4 questions, code-graded (+ the 4 judged rules via gpt-4.1 on
  OpenRouter), on B before and after SDF. If stage 1 (lr 1e-4) wipes out B's controllability, the comparison is void.
- Also reported: deception rate, CoT length, empty-CoT and evasive rates.

## Steps and gates

1. **Documents** (gpt-5-mini, OpenRouter, Haskins' `gen_data.py`): about 2,000 behavioural (12 facts × 75 × 2 runs)
   and 1,200 monitoring (16 facts × 75, subsampled to 1,000). Run 50 first to measure cost per document.
   Gate: if the cost is over $0.01 per document, stop and re-budget. Then check that no document contains a CoT
   example (his autorater filter).
2. **Controllability of B before SDF**: the v2 check (also confirms the checkpoint loads).
3. **Stage 1** on B (and base): save state every epoch; sweep epochs on 100 validation scenarios.
   Gate: the deception rate must be high (his: 94 %), otherwise the behaviour was not installed.
4. **Stage 2** branches from the selected stage-1 epoch; sweep epochs.
5. **Final eval** of the selected checkpoints on the 900 non-validation scenarios plus the no-reasoning baseline;
   monitor and counterfactual autorater.
6. **Controllability of B after SDF.**
7. Write-up section in `STEGO_EXPERIMENT.md`, website and deck.

## Budget

Assumed prices: gpt-5-mini $0.25 / M input, $2 / M output (includes its reasoning tokens); gpt-oss-120b on Tinker
about $0.5 / M training tokens and about $0.2–0.45 / M sampling (from our screen's actual spend). Documents about 700
tokens each.

| item | volume | B only (B-MA, B-BO) | + base-MA, base-BO |
|---|---|---:|---:|
| documents (OpenRouter) | ~3,200 docs + ideas + repairs | $15 | (shared) $15 |
| SDF training (Tinker) | 3 stages × 1,000 docs × 5 epochs ≈ 10.5 M tokens per model | $5 | $10 |
| epoch sweeps (Tinker) | 15 checkpoints × 100 scenarios per model | $1 | $2 |
| final eval + no-reasoning (Tinker) | 2 × (1,000 + 1,000) per model | $2 | $4 |
| monitor + counterfactual (OpenRouter) | ~2,000 gpt-5-mini calls per model | $3 | $6 |
| controllability check | ~350 prompts + judge | $1 | $1 |
| **total** | | **≈ $27** (OpenRouter $19, Tinker $8) | **≈ $38** (OpenRouter $22, Tinker $16) |
| with 30 % contingency | | $35 | $50 |

OpenRouter balance on 2026-10-14: about $72. Time: about 1 hour for documents and 1–2 hours per training stage, so
roughly a day end to end with the base arms run in parallel.

## Risks

- **Regenerated documents** differ from Haskins'. The base arms control for this; asking Haskins for his document
  sets would remove it.
- **SDF may undo controllability training** (stage 1 is a high learning rate on 5,000 document passes): measured in
  step 6.
- **Epoch selection picks the best undetected epoch**, which favours whichever arm is noisier; the per-epoch tables are
  reported for every arm, as in his appendix.
- **No-reasoning for gpt-oss** cannot switch reasoning off; we prefill an empty analysis channel, which may differ from
  his method (not described for gpt-oss).
