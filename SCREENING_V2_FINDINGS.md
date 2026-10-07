# Screening base models for the unlearning experiment: findings

*2026-10-07. Step 1 of `UNLEARNING_V2_PLAN.md`: which base models control their own chain of thought well enough
that removing the ability, and testing whether it survives elicitation, can be measured? Rules: the 40 v2 rules
(`CONDITIONS_V2.md`). Script: `scripts/v2/screen.py`; table and figures: `scripts/v2/screen_report.py`.*

## Why screen

The unlearning experiment asks whether a model's **own** ability to control its chain of thought can be removed, and
whether that removal survives elicitation (best of k, prefill, better prompts, a little fine-tuning). That can only be
measured on a model that has the ability to begin with:

- **Something to remove.** If base follows almost no rule, an unlearned model at 0 % looks the same as base, and
  "survives elicitation" cannot be told apart from "there was never anything to elicit". gpt-oss-20b (0.9 % in OpenAI's
  CoTControl study) is in this position.
- **Genuine control, not a side effect.** A rule the model satisfies anyway (chance rate), or passes by quoting the
  instruction (restating), would "disappear" after training for reasons unrelated to controllability. So scores are
  taken above chance and checked without restating traces.
- **Spread over both halves of the rules.** Unlearning trains on half the rules and tests whether the loss spreads to
  the other half. If the model's control sits only in the half being unlearned, the held-out readout has nothing to
  lose.
- **Room for elicitation.** Best of 3 shows how much more a model can do when pushed; an unlearned model should not
  get that back.

Screening is cheap compared with the experiment itself (one inference pass per model, no training), so it decides
which 2–3 models are worth the unlearning runs.

## Method

For each untouched base model:

1. **Chance rates.** 200 reasoning traces with no rule in the prompt. They calibrate the model's thresholds (N, M, T, W)
   and give each rule's chance rate: how often the model satisfies it without being asked.
2. **Asked.** 40 rules × templates T1–T3 × 10 questions × 3 samples = 3,600 prompts, one rule per prompt. The
   questions are a subset of the v2 evaluation grid used for gpt-oss-20b and Gemma.
3. **Scores**, macro over operations:
   - **one sample:** the first sample;
   - **best of 3:** the rule counts as followed if any of the three samples follows it;
   - **above chance:** each rule's score minus its chance rate (floored at 0);
   - **without restating:** one sample, scored only on traces that do not restate the rule. Inclusion rules ("use 4
     transition words", "include a marker") can be passed by quoting the instruction.

Gemma-4-31B and Qwen3-32B ran on vLLM with 4-bit weights (skynet3/skynet4); the other four ran on Tinker in full
precision. Sampling followed each model's recommended thinking settings (gpt-oss-120b and Qwen3.8-27B at medium
reasoning effort).

## Results

![Chance, one sample, best of 3](figures/screen_v2_models.png)

| model | above chance: one sample / best of 3 | above chance, traces that do not restate the rule | rules ≥ 20 points above chance (best of 3), families | accuracy | restates the rule | median reasoning, words |
|---|---:|---:|---|---:|---:|---:|
| **Gemma-4-31B** | 16 / **22** | **18** | **15, 7** | 89 | 55 % | 399 |
| **Qwen3.8-27B** | 11 / 17 | **16** | 10, 7 | 89 | 72 % | 219 |
| DeepSeek-V3.1 | 14 / 18 | 14 | 9, 5 | 90 | 59 % | 353 |
| Qwen3-32B | 11 / 16 | 11 | 13, 5 | 89 | 8 % | 330 |
| gpt-oss-120b | 10 / 13 | 11 | 6, 4 | 88 | 72 % | 193 |
| Nemotron-3-Nano | 10 / 12 | **2** | 7, 5 | 84 | 92 % | 623 |

Chance rates are 1–2 % for every model. The "without restating" score covers only rules with at least 5 such traces.

1. **Base controllability is modest everywhere**: 10–16 % above chance with one sample, 12–22 % with best of 3.
   Gemma-4-31B is highest.
2. **Restating matters for some models.** Nemotron-3-Nano restates the rule in 92 % of traces, and without those
   traces its controllability collapses to 2 %. Gemma (18) and Qwen3.8 (16) keep or gain: their control is genuine.
3. **Every model is good at the same three rules** (include a marker, all 7 coordinating conjunctions, 4 transition
   words: 37–100 points above chance). Beyond those, each model has a few of its own: Gemma style and word length, DeepSeek capitals and
   language, Qwen3.8 lowercase and a fixed opening sentence, Qwen3-32B word bans.
4. **No model controls structure or word layout** (XML, JSON, lists, tables, one word per line, filler words,
   brackets): under 10 points above chance for all six.

![Restating the rule](figures/screen_v2_restating.png)

Without restating traces, Gemma and Qwen3.8 keep or gain; Nemotron falls from 10 to 2. Qwen3-32B hardly ever restates (8 %),
so its two scores are the same.

![Per family](figures/screen_v2_families.png)

Inclusion is strong for every model (70–76); structure is 0 for all. The rest is model-specific: Gemma style (44) and
bans (38); DeepSeek case (29); Qwen3-32B bans (31) and length (27); gpt-oss-120b letter statistics (25); Qwen3.8
position (18).

![Every rule, every model](figures/screen_v2_rules.png)

## Where the controllability sits: the two halves of each split

Unlearning trains on one half of the rules and tests the other. Both halves need controllability to lose.

| best of 3 above chance, % | by-family: unlearned half / held-out half | within-family: unlearned half / held-out half |
|---|---:|---:|
| Gemma-4-31B | 25 / **20** | 26 / **19** |
| Qwen3.8-27B | 25 / 8 | 21 / 12 |
| DeepSeek-V3.1 | 26 / 9 | 24 / 11 |
| Qwen3-32B | 25 / 7 | 15 / **17** |
| gpt-oss-120b | 19 / 8 | 18 / 9 |
| Nemotron-3-Nano | 16 / 9 | 16 / 9 |

![Halves](figures/screen_v2_halves.png)

Counting rules at least 20 points above chance instead (unlearned / held out): Gemma 7 / 8 by family and 8 / 7 within
family; Qwen3.8 6 / 4 under both; DeepSeek 7 / 2 under both; Qwen3-32B 10 / 3 by family and 6 / 7 within family.

Only Gemma has substantial controllability in the held-out half under either split. For the other models most of it
sits in the half the by-family split would unlearn (the inclusion rules are a training family there); the
within-family split balances Qwen3-32B and partly Qwen3.8.

## Candidates

| rank | model | why | where it can run |
|---|---|---|---|
| 1 | **Gemma-4-31B** | most controllability, broadest (15 rules, 7 families), genuine, balanced under both splits | local 32 GB GPU only (not on Tinker) |
| 2 | **Qwen3.8-27B** | genuine control over 7 families; held-out half weaker (8–12 %) | **Tinker** (screening and LoRA training) |
| 3 | Qwen3-32B | balanced only with the within-family split; little restating | local GPU only |
| 4 | DeepSeek-V3.1 | control concentrated in the unlearned half (7 / 2) | Tinker |
| – | gpt-oss-120b | too narrow (6 rules) | Tinker |
| – | Nemotron-3-Nano | control is mostly restating the rule | Tinker |

**Recommendation:** run the unlearning experiment on **Qwen3.8-27B on Tinker** now (within-family split, the more
balanced one for it), and on **Gemma-4-31B** when a local GPU is free.

## Cost

**Screening (actual, from the token counts):**

| model (Tinker) | prompt tokens | sampled tokens | mean reasoning + answer, tokens | cost |
|---|---:|---:|---:|---:|
| DeepSeek-V3.1 | 0.48 M | 5.77 M | 1,518 | $25 |
| Qwen3.8-27B | 0.53 M | 4.73 M | 1,244 | $28 |
| Nemotron-3-Nano | 0.55 M | 8.34 M | 2,193 | $9 |
| gpt-oss-120b | 0.72 M | 2.60 M | 684 | $2 |
| **total** | | | | **$64** |

Plus about $1 per model for the gpt-4.1 judge. Gemma and Qwen3-32B ran on our own GPUs.

**Unlearning experiment on Qwen3.8-27B via Tinker (estimate):** Tinker prices for Qwen3.8-27B are $1.86 per million
prompt tokens, $5.595 per million sampled tokens and $4.10 per million training tokens; reasoning about 1,250 tokens
per prompt, as in screening.

| step | volume | estimate |
|---|---|---:|
| the model's own unconstrained traces for the training data | ~900 prompts | $6 |
| training U and C, two seeds each (4 LoRA runs, one epoch) | ~900 examples × ~1.5k tokens × 4 | $22 |
| plain evaluation grid: 40 rules × 6 templates × 20 questions on base, U ×2, C ×2 | 24,000 prompts | $175 |
| elicitation on base, U and C (E0–E9 on T1, 10 questions per rule) | ~12,000 prompts | $85 |
| relearning attack: 2 doses × U and C, re-evaluated on T1 | ~5,000 prompts + small training | $35 |
| **total** | | **≈ $320** |

Fine-tuned models usually reason more briefly, which would lower this by about a third. Halving the evaluation grid to
10 questions per rule would bring it to about $200. Gemma-4-31B is not on Tinker, so its run needs a local GPU instead
(about 2–3 GPU days).

## Not screened

- **OLMo-3.1-32B-Think:** started on skynet4, which became unreachable mid-run; results not recovered.
- **GLM-4.7-Flash, Magistral-Small-2509, Qwen3.6-35B-A3B:** never ran (skynet4 down; the Qwen3.6 NVFP4 build also
  failed to serve). Qwen3.6-35B-A3B is on Tinker and could be screened there.
- **gpt-oss-20b:** skipped; its base controllability is known to be very low (0.9 % in OpenAI's CoTControl study,
  2–3 % on our held-out rules).

## Caveats

- **10 questions × 3 templates per rule:** a single rule's score is uncertain by about ±15 points; the macro scores are
  much tighter.
- **Different serving stacks:** Gemma and Qwen3-32B on 4-bit weights via vLLM; the rest in full precision via Tinker.
- **Reasoning effort:** Qwen3.8-27B was screened at medium effort, not Tinker's default (maximum). Longer reasoning
  is reported to lower controllability, so its default setting may score lower.
- **Four rules are judged by gpt-4.1** (a series of questions, pirate speak, sports commentator, opening summary);
  their chance rates use 40 judged traces each.
