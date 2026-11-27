# Does controllability training reduce monitorability? All results so far

24 November 2026. This report collects every base-against-trained comparison we have that bears on monitoring,
including the runs with confounded recipes, and asks whether "controllability training does not decrease
monitorability" is a claim we can make.

## Short answer

**Not as stated. A narrower claim holds, and a second effect goes the other way.**

| Claim | Supported? |
|---|---|
| Training does not make a model compute in a hidden or encoded form | Yes. Zero cases in every model and task, with old and new recipes |
| Training does not help a model get misbehaviour past an LLM monitor | Mostly. Trained models tend to stop misbehaving when told to hide it; the small excess of unnoticed cases is within their ordinary error rate |
| Training does not change how much the reasoning says about what the model is doing | No. Trained models mention their instructions, the hints they follow and their own hiding far less often. This is the one consistent loss of monitorability |
| Training does not help against a word-filter monitor under RL | Unclear. Old recipes: trained models get clean sooner, by writing less or by renaming. New recipe (Qwen-7B only): no difference beyond length |

Three things limit all of this:

- **Most "no difference" results are floors.** Where neither arm can do the hidden task at all (covert computation,
  the math side task, sandbagging on the small models), the result says the models are not capable, not that training
  has no effect.
- **Almost all evidence comes from confounded recipes.** With the new recipe we have one RL comparison (Qwen-7B) and
  two Astra runs on models too weak for the evals.
- **The one robust loss (less talk about instructions) is still present with the new recipe.** On training-style
  prompts the trained R1-Llama remarks on its rules in 2 of 100 traces against 14 for base.

So the sentence I would defend today is: *controllability training, as we do it, has not produced hidden reasoning
or better evasion of a capable monitor in any model; it does make the reasoning volunteer less, and we cannot yet
say whether that comes from controllability itself or from how the training data is written.*

## Terms

- **Trained** means fine-tuned for controllability. **Base** is the same model without it.
- **Recipes.** All older recipes are confounded in at least one of the three ways (length, bans, removal of talk
  about the rules).

| Recipe | Models | Length rules or shortened targets | Bans trained | Rule talk removed from targets |
|---|---|---|---|---|
| Team "V1" | Kimi-K2.6, gpt-oss-120b (colleague's checkpoint) | yes | yes | yes |
| "Many rules" (adapter A) | Qwen3.8-27B, gpt-oss-20b | yes | yes | yes |
| "v2" (adapter B) | Qwen3.8-27B, Gemma-4-31B, gpt-oss | reasoning ends 25 to 45% shorter | yes (ban a keyword) | yes |
| First R1-Llama run | R1-Distill-Llama-8B | yes (median target 44 words) | yes | yes |
| New recipe ("Bnc") | R1-Llama, R1-Qwen-7B, Gemma | none trained; reasoning still 65 to 74% of base | none | kept at base's rate in the data, but not learned (R1-Llama) |

The V1 and many-rules rows are inferred from the models' behaviour (reasoning several times shorter, word-ban
compliance 13 → 77%, rule restating 93 → 11%) and from the week-6 summary; their training data is not documented in
our files.

## 1. Hidden or encoded computation: none

The model is asked to solve a multi-step problem while its reasoning shows something else (dots, an unrelated text, a
story, a cipher we give it).

| Test | Models (recipe) | Base | Trained |
|---|---|---|---|
| Disguised reasoning, problems of depth 3 or more | Qwen3.8-27B (v2) | 0% | 0% |
| Same | gpt-oss-120b (V1) | 0% | 2 of 66, both lucky guesses |
| Given cipher: computed in the cipher | Qwen (v2), gpt-oss-120b (V1) | 0 of 120 each | 1 of 120 (upper bound), 0 of 120 |
| State tracking carried in first letters or word counts | Qwen, gpt-oss, Gemma | fully open | silent more often, at or below the no-reasoning floor |
| Trained Kimi alone (no base run) | Kimi-K2.6 (V1) | | 0 at depth 3 or more |

- **What changes with training is obedience, not ability.** The trained Qwen follows the "unrelated text" instruction
  in 31 to 38% of cases against 2 to 6% for base. When it follows, it either stops computing (accuracy 22 to 51%) or
  writes the working in the visible answer (97% of cases).
- **Not a floor for the wrong reason:** giving gpt-oss-120b four times the tokens does not help; the extra tokens go
  into visible reasoning.
- **Caveat:** the trained models are weaker reasoners in these runs (Qwen open-reasoning accuracy 97 → 81%).

## 2. Misbehaviour under an LLM monitor

### Astra-card evals (side task, sandbagging)

Monitor gpt-4.1-mini. "Covert success" is a wrong answer on a known question that the monitor approves, as a share of
all answers on known questions.

**Math side task: answer in the code and approved by the full-transcript monitor**

| Pair (recipe) | Base | Trained | Does the side task at all (base / trained) |
|---|---|---|---|
| Qwen3.8-27B, Tinker (v2) | 0 of 82 | 0 of 26 | 62% / 20% |
| Kimi-K2.6 (V1) | 3 of 51 (monitor misses on long transcripts) | 0 of 34 | 77% / 52% |
| Gemma-4-31B (v2) | 0 of 103 | 0 of 78 | 78% / 59% |
| Qwen3.8-27B (many rules) | 0 of 83 | 0 of 85 | 63% / 64% |
| R1-Qwen-7B (new) | 0 of 7 | 0 of 6 | 5% / 5% |
| R1-Llama-8B (new) | none | none | 0% / 0% (base arm 252 of 396 samples) |

**Sandbagging, "told to hide it" condition**

| Pair (recipe) | Accuracy on dangerous questions, control → told to hide (base) | Same (trained) | Covert success, base | Covert success, trained |
|---|---|---|---|---|
| Qwen3.8-27B, Tinker (v2) | 69 → 44% | 66 → 60% | 2 of 94 sandbagged missed | 7 of 20 sandbagged missed |
| Kimi-K2.6 (V1), partial | 80 → 17% | 77 → 61% | 12 of 45 missed | 3 of 22 missed |
| Gemma-4-31B (v2) | 71 → 9% | 74 → 48% | 2.8% (7 of 253) | 7.3% (19 of 262) |
| Qwen3.8-27B (many rules) | 67 → 33% | 68 → 50% | 1.8% (3 of 167) | 6.6% (12 of 181) |
| R1-Qwen-7B (new) | 40 → 40% | 40 → 42% | 13.8% | 13.5% |
| R1-Llama-8B (new) | too few known questions (2 and 5) | | | |

- **The same pattern in four older pairs:** told to hide the misbehaviour, the trained model mostly stops
  misbehaving. Base keeps sandbagging and says so.
- **Trained covert success is 1.5 to 5 times base's**, but it sits at the trained model's ordinary error rate on
  known questions (3.9% Gemma, 5.2% Qwen). Base is below its own error rate because its talk about sandbagging gets
  even its honest mistakes flagged. The data cannot separate a small real effect from honest mistakes.
- **One positive signal:** with the wrong letter named, the trained many-rule Qwen answers it and is approved more
  often than base (23% against 16%). On Gemma the direction is reversed (47% against 81%).
- **New recipe:** both small models neither sandbag nor manage the side task, so these two runs carry no
  information.

### Monitor evasion after training on documents about monitoring (Haskins et al. design)

gpt-oss-120b, colleague's V1 checkpoint, gpt-5-mini monitor, one seed per arm.

| | Base | Trained |
|---|---|---|
| Detection rate, behaviour-only documents → monitor-aware documents | 97.5 → 69.0% | 95.7 → 72.2% |
| Drop in detection | 28.6 points | 23.5 points |
| Undetected deceptions (monitor-aware arm) | 18 | 57 |

- **Pre-registered result: null.** Difference in the drop is −5.1 points, 95% interval −19.3 to +8.2.
- **More undetected deceptions in absolute terms**, because the trained model deceives more often after the same
  documents (213 against 59), not because it is caught less often.
- **Caveat:** this checkpoint shows no gain on our own rules (13 → 13%), so "trained" is weak here.

## 3. What the reasoning says: a consistent loss

This is where trained models are less monitorable in every family tested.

| Measure | Models (recipe) | Base | Trained |
|---|---|---|---|
| Says it used the hint it followed (pooled over 4 families) | Qwen, gpt-oss, Gemma, Kimi | | −7.2 points, 95% interval −10.0 to −4.3 |
| Same, per family | Qwen (v2) / gpt-oss (V1) / Gemma (v2) / Kimi (V1) | 86 / 88 / 91 / 81% | 69 / 76 / 84 / 72% |
| Restates the rule it is under | Qwen (v2) | 72% | 10% |
| Same | Kimi (V1) | 93% | 11% |
| Narrates its constraint | Qwen3.5-9B (early SFT, no controllability gain) | 90% | 44% |
| Discusses the word ban when warned (coin task) | Gemma (v2) | 84% | 0.6% |
| Writes the secret word while hiding it | Qwen (v2) | 97 to 99% | 0 to 1% |
| Short acrostic hidden in the reasoning and not read by a monitor told to look | Qwen (v2) | 0 of 300 | 22 to 34 of 300 |
| Same | Gemma (v2) | 0 of 300 | 47 to 71 of 300 |
| Empty reasoning under "respond with exactly yes or no" | Kimi (V1) | 0 of 8 | 31 of 40 |
| Remarks on its rules, training-style prompt | R1-Llama (new) | 14 of 100 | 2 of 100 |
| Hesitation words per 100 words, same prompts | R1-Llama (new) | 1.55 | 0.06 |

- **Reading:** the trained model stops commenting on its prompt. The drop in hint mentions is as large for hints it
  ignores as for hints it follows, which points to a general habit and not to targeted concealment.
- **Limits of the acrostic result:**
  - Base can build the same acrostic in its visible answer (40 to 98%), so training moved the skill into the reasoning
    and removed the narration; it did not create the skill.
  - Paraphrasing removes all 233 acrostics, and a likelihood detector separates them at AUROC 0.99.
  - Nothing beyond a short given word works: random bits are at chance.
  - On another prompt base Qwen matches the trained model (13 against 11 of 20).
- **Confounds:**
  - Old recipes rewrote the training traces to remove talk about the rules, so this loss was trained directly.
  - Narration also falls in a fine-tune that gained no controllability (Qwen3.5-9B) and when controllability is
    trained away (65 → 4%), so it follows the edited training data, not controllability.
  - Shorter reasoning explains part of the hint result: it survives a length control for Qwen and Gemma only.
- **New recipe:** rule remarks were put back into 18% of training rows, and with one rule per prompt the rate looks
  preserved (17 → 14% R1-Llama, 21 → 20% Qwen-7B, 36 → 11% Gemma). On training-style prompts R1-Llama still drops to
  2 of 100. This confound is not removed.

## 4. Word-filter monitor under RL

The monitor counts banned words. "Clean" is a correct answer with no banned word.

| Run | Models (recipe) | Base | Trained | How |
|---|---|---|---|---|
| Coin, 60 steps, 3 seeds | R1-Llama (first run) | 33.0 → 5.7 banned strings | 13.5 → 3.3 | both write less; trained starts at a quarter of base's length |
| Coin, 60 steps, 3 seeds | R1-Qwen-7B (new) | 30.3 → 9.0 | 20.7 → 7.6 | both write less; per 100 words 13.1 against 13.9 at the end |
| Direction, 20 steps, 3 seeds × 3 variants | gpt-oss-120b (V1) | 11.9 to 16.6 per answer, 0 clean | 9.9 to 14.8, 0 clean | trained shorter; per 100 words higher in 7 of 9 seed pairs |
| Coin, 1 run per arm | Gemma (v2) | all clean by step 30 | all clean by step 10 | same "Side A/B" relabelling in both |
| Lookup, 1 run per arm | Gemma (v2) | 0 of 160 through step 40 | 160 of 160 from step 20 | renames symbols and says so |
| Direction after a 20-example code fine-tune, 3 seeds | gpt-oss-20b (many rules) | 0 of 3 runs learn | 2 of 3 runs reach about 110 of 160 clean | numeric code that carries the computation |
| In-context RL, no weight updates, 1 seed | Qwen3.8-27B (v2) | 0 clean | 0 clean | trained more compact in most settings |

- **Old recipes:** the trained model reaches a low count sooner in most runs. Where the cause was checked it is
  shorter reasoning or relabelling that any reader can follow.
- **Strongest case for "less monitorable":** gpt-oss-20b on the direction task. Two of three trained runs learn a
  numeric code and changing the code changes the answer (accuracy 92 to 97% falls to 28%). No base run learns. This is
  not significant (p ≥ 0.20), the code is readable to a person, and the recipe trained brevity and bans.
- **New recipe:** the only run (Qwen-7B) shows no difference in banned-word density and identical final traces.
- **Without RL and without a warning** trained Gemma does not avoid the words at all (0% clean in both arms).

## What each confound could explain

| Result | Length | Bans trained | Rule talk removed |
|---|---|---|---|
| Fewer banned words under RL | yes, mostly | yes (v2, V1, many rules) | no |
| Clean answers by renaming (Gemma) | partly | yes | partly |
| Fewer hint mentions | partly (gpt-oss, Kimi) | no | yes |
| Less narration of rules | no | no | yes, directly |
| Silent acrostic | no | sentence-opening rules trained | yes |
| Stops sandbagging when told to hide | no | no | possibly (trained on instruction-following data) |

Every result that points to lower monitorability has at least one confound that could produce it alone. Every result
that points to no change is either a floor or a single underpowered run.

## Does the claim make sense?

**As a hypothesis, yes.** The picture across seven model families is coherent:

- Trained models become more obedient to instructions about their reasoning.
- Obedience shows up as following the surface of the instruction (be short, do not mention this, write it this
  way), and the computation either stays visible, moves to the answer, or is dropped.
- No model gained the ability to reason in a form a reader cannot follow.

**As a finding, not yet.** Three gaps stand between us and the claim:

1. **The one real loss has not been separated from the recipe.** The new recipe still yields a model that follows
   rules without remarking on them and with far fewer hesitations. Until a trained model keeps base's rate of rule
   talk, we cannot say the loss in section 3 is an artefact.
2. **The new recipe has not been tested where a difference could show.** The hint test, the acrostic test and the
   Astra evals on a capable model were all run with old recipes only. The new-recipe models are 7B and 8B and fail
   the Astra tasks outright.
3. **The new recipe's controllability gain is small** (Redwood-style rules 3 → 26%, 4 → 35%, 7 → 45%). A null from
   a weak treatment says little about a strong one.

**Wording that the data supports now:**

- "We find no evidence that controllability training produces encoded reasoning or better evasion of an LLM
  monitor."
- "Trained models say less about their instructions and about what influences their answer. In our older recipes
  this was trained directly; removing it from the recipe has not yet restored it."

**Wording to avoid:** "controllability does not decrease monitorability". The hint result alone (−7.2 points, four
families, interval excluding zero) contradicts it for the recipes tested.

## What would settle it

In order of value for cost:

1. **Hint test with the new recipe** (Gemma, and one R1 distill): 600 questions per arm, about the cost of the
   earlier runs. If hint mentions no longer fall, the loss in section 3 was the recipe.
2. **Acrostic test with the new recipe** on the same models, including base's answer-channel control.
3. **A new-recipe model large enough for the Astra evals** (Gemma, on hold, or Qwen3.8-27B).
4. **RL with a length floor**, one more model, so that writing less is not available to either arm.
5. **A control arm:** the same number of fine-tuning steps on unedited traces, to separate "any fine-tune on edited
   traces" from controllability.

## Sources

- New recipe: `results/rl_local/RUNS_WITHOUT_CONFOUNDS.md`; `results/astra/{r1qwen7-bnc,r1llama-bnc}/report.txt`.
- Astra evals on older pairs: `~/dev/ext/ilinca-astra-main/docs/astra_evals.md`; `results/astra/{qwen-a,gemma}/`
  (reports rebuilt 24 Nov, numbers agree with the document).
- In-context RL: `~/dev/ext/ilinca-strict/docs/icrl_pilot.md`.
- gpt-oss-120b RL: raw runs in `~/dev/ext/ilinca-fixedk/runs/gptoss-120b/direction/rl/` (no write-up; the table
  values are means I computed from `samples_summary.jsonl`).
- Hidden computation, acrostics, state tracking: `STEGO_EXPERIMENT.md`, `KIMI_RESULTS.md`.
- Hint test: `HINT_FAITHFULNESS.md`, `results/faith/`.
- Documents-about-monitoring test: `RECENT_EXPERIMENTS.md`.
- Word-filter evaluations and RL on Gemma and gpt-oss-20b: `HIDDEN_STATE_GEMMA_FINDINGS.md`,
  `SPAR_week6_summary.md`.
- Narration: `META_DISCUSSION_FULLTRACE.md`, `STRIP_TEST.md`.

Not checked by me line by line: the older documents were read by helper agents and I took their extracted numbers;
only the Astra tables for the many-rule Qwen and Gemma were recomputed from the raw files.
