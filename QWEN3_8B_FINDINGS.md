# Multi-constraint SFT on Qwen3-8B: findings

*Second model for the multi-constraint experiment. Same six constraints, pairing rules, editor and LoRA recipe
as `MULTI_CONSTRAINT_FINDINGS.md` (Qwen3.5-9B); design in `QWEN3_8B_PLAN.md`; generated tables and figures in
`QWEN3_8B_RESULTS.md`. Six arms were trained (S1, P2, T3, Q4, Q5, M5 = one to five constraints per example);
within the 24-hour budget, base, S1, T3 and Q5 were evaluated at step-final on the full suite and S1 and T3 at
step-60 on single-constraint prompts. ± are 80 % Wald intervals; "joint" = every constraint in the prompt
satisfied, binary, over rollouts with a closed think block.*

## Headline

**Training on several constraints per example again beats single-constraint training in-domain, and on
this model it produces the first binary transfer to CoTControl: 12 % of single-mode CoTControl prompts fully
satisfied after Q5 (five constraints per example) and 8 % after T3 at step-60, against ≤ 1 % for S1 and 0.3 %
for base. The transfer is concentrated in four modes (JSON wrapping, lowercase, uppercase, end-of-sentence),
is absent inside multi-mode CoTControl prompts, and for T3 it is larger at step-60 than at step-final.**

| Qwen3-8B, step-final unless noted | ReasonIF k=1 | k=3 all | k=3 held-out | k=5 | CoTControl k=1 |
|---|---:|---:|---:|---:|---:|
| base | 11.0 ± 3.7 | 0.0 | 0.0 | 0.0 | 0.3 ± 0.4 |
| S1 | 42.0 ± 5.8 | 17.0 ± 3.9 | 18.4 ± 8.1 | 29.4 ± 10.0 | 0.8 ± 0.6 |
| T3 | **51.7 ± 5.9** | 24.5 ± 4.4 | 25.6 ± 9.0 | 30.8 ± 9.5 | 2.1 ± 0.9 |
| T3 step-60 | 34.5 ± 5.6 | — | — | — | **8.3 ± 1.8** |
| Q5 | 42.5 ± 5.8 | **25.6 ± 4.5** | **28.9 ± 9.4** | **41.0 ± 10.1** | **12.1 ± 2.1** |

CoTControl k=3 and k=6 prompts: 0 % joint for every checkpoint.

![ReasonIF joint by level](figures/q3_8b_joint_reasonif.png)
![CoTControl k=1 joint](figures/q3_8b_joint_cotcontrol_k1.png)

## Findings against the predictions

**1. The starting floor is not higher, and binary transfer appeared anyway.** The plan's first prediction
rested on Qwen3-8B having more baseline CoTControl compliance than Qwen3.5-9B. It does not: base is at 0.3 %
on CoTControl singles (one word-suppression rollout in 400) and 11 % on ReasonIF singles, with only
number_words (53 %) and reasoning_language (15 %) above zero, exactly the two Qwen3.5 base could do. The
conclusion of the prediction nevertheless held in part: with the same recipe that gave ≤ 2.5 % on Qwen3.5,
Q5 reaches 12.1 % and T3 step-60 8.3 % on CoTControl singles, while S1 stays at ≤ 1 % at both checkpoints.
The gap between S1 and the multi arms on the transfer side is the effect the whole line of work was after.

**2. Where the transfer sits.** Per mode, binary, CoTControl singles:

| mode | base | S1-final | T3-60 | T3-final | Q5-final |
|---|---:|---:|---:|---:|---:|
| json_format | 0 | 0 | **38** | 2 | **55** |
| lowercase_thinking | 0 | 2 | 15 | 5 | **25** |
| uppercase_thinking | 0 | 0 | 15 | 10 | **18** |
| end_of_sentence | 0 | 2 | 0 | 0 | **18** |
| word_suppression | 2 | 0 | 12 | 2 | 0 |
| the other five | 0 | 0–2 | 0–2 | 0 | 0–2 |

JSON wrapping is the largest single gain and the most surprising: no arm saw a JSON example. The passing
rollouts are genuine, a JSON object with a `"reasoning"` key holding the full reasoning (median 2,400
characters), not short or empty traces. Continuous scores move in the same places: uppercase 0.06 → 0.77,
end_of_sentence 0.00 → 0.47, JSON 0.00 → 0.64 for Q5. Macro over the ten modes, base 0.28 → Q5 0.51, and
excluding uppercase (the mode closest to the trained `capital`) 0.31 → 0.48, so the gain is not the
uppercase twin alone. ignore_question, meow, alternating case, multiple-word suppression and repeat
sentences do not move for any arm.

The same per mode on the continuous score:

![CoTControl continuous per mode](figures/q3_8b_cotcontrol_continuous_modes.png)

![CoTControl per-mode singles](figures/q3_8b_cotcontrol_modes.png)
![CoTControl continuous macro](figures/q3_8b_cotcontrol_continuous.png)

**3. No transfer inside multi-mode CoTControl prompts, but the modes that transfer are satisfied there too.**
Joint compliance on k=3 and k=6 CoTControl prompts is 0 % for every checkpoint. Per mode inside those
prompts, Q5 satisfies lowercase in 40 % (k=3) and 75 % (k=6) of the rollouts that ask for it, uppercase 34 /
42 %, end_of_sentence 25 / 31 %, JSON 25 % (k=3). The joint stays at zero because every combination also
contains at least one of the modes that never transfer, and all three k=6 sextuples contain ignore_question
and meow. So the model applies the transferred formats when they are one of several, which is what the
ReasonIF side taught it, but the untouched modes cap the all-or-nothing score.

![CoTControl modes inside combinations](figures/q3_8b_cotcontrol_inside_combos.png)

**4. In-domain: the S1 → T3 gain replicates; Q5 does not extend it on singles.** On ReasonIF singles T3
beats S1 by 10 points (52 vs 42 %; on Qwen3.5 it was 26 points, 52 vs 26 %). On triples, seen and held-out,
T3 and Q5 are tied at 25–29 % against S1's 17–18 %. On quints, Q5's own level, Q5 leads at 41 % against
30 % for both others. But on singles Q5 (42.5 %) is level with S1 and below T3: the arm trained on the two
nearly identical five-constraint combinations does not generalise to single rules as well as the arm
trained on twelve varied triples. This is the plateau-then-drop the plan's prediction 2 anticipated, and it
says the diversity of combinations matters, not only their size. Held-out triples score as high as seen
ones for every arm (18 / 26 / 29 % held-out vs 17 / 25 / 26 % seen), as on Qwen3.5.

Per constraint on single-constraint prompts, all six checkpoints:

![ReasonIF per-constraint singles](figures/q3_8b_reasonif_constraints.png)

Every evaluated ReasonIF condition at step-final, held-out combinations marked †. The one condition no arm
solves is no_comma + end_of_sentence + capital, and the two five-constraint combinations separate cleanly:
the end_checker variant (45–55 %) is far easier than the end_of_sentence variant (12–26 %):

![ReasonIF condition heatmap](figures/q3_8b_condition_heatmap.png)

Per-constraint compliance rises with the number of rules in the prompt for all three trained arms
(`QWEN3_8B_RESULTS.md`, per-constraint by k): for S1 as well this time (capital 15 → 25 → 41 %, no_comma
10 → 25 → 62 %), where on Qwen3.5 S1 reversed. The base model shows the same for end_checker and no_comma
at low levels.

![per-constraint by number of rules](figures/q3_8b_per_constraint_by_k.png)

**5. Step-60 vs step-final: in-domain keeps rising for T3, transfer peaks early.** In-domain, the Qwen3.5
pattern replicates: S1 gains little after step-60 (39 → 42 %) while T3 keeps gaining (34.5 → 51.7 %). On
the transfer side the picture inverts for T3: 8.3 % at step-60 falls to 2.1 % at step-final, with JSON
38 → 2 % and lowercase 15 → 5 %, and the continuous macro 0.42 → 0.36, while S1 is flat at ≤ 1 %. One
reading: the first 240 triple-constraint examples teach "apply every formatting rule in the prompt", and
the remaining 675 specialise that skill to the ReasonIF template and its six rules. One seed and two
checkpoints cannot settle it; the intermediate T3 checkpoints (steps 30 to 210) and Q5 step-60 are on
disk and would show the trajectory for about an hour of GPU each on the CoTControl singles alone.

![step-60 vs step-final](figures/q3_8b_step60_vs_final.png)

**6. Costs.** Accuracy on the ReasonIF questions falls from 53 % (base) to 45–52 % depending on the arm;
on the CoTControl questions it is unchanged (46–51 % vs 48 %). Truncation at 32k is 3–23 rollouts per
checkpoint. Base Qwen3-8B answers ignore_question prompts with an empty think block (all 40 singles, 79
rollouts in all), which the pipeline counts as ungradeable; every trained arm thinks again on those prompts
and scores 0 % on the mode.

![accuracy and truncation](figures/q3_8b_accuracy_truncation.png)

Reasoning-language compliance by requested language. Chinese, Hindi and Arabic were never in any arm's
training data; with two to three prompts per language per checkpoint this is indicative only, but every
trained arm reaches Chinese and Hindi, and Arabic is the one language that fails for S1 and Q5:

![reasoning_language by language](figures/q3_8b_language_breakdown.png)

## Qwen3.5-9B against Qwen3-8B, same constraint set and recipe

![Qwen3.5-9B vs Qwen3-8B](figures/q3_8b_vs_qwen35.png)

| step-final | ReasonIF k=1 | ReasonIF k=3 | CoTControl k=1 binary | CoTControl k=1 continuous |
|---|---:|---:|---:|---:|
| Qwen3.5-9B base / S1 / T3 | 6 / 26 / 52 | 0 / 7 / 39 | 0 / 0 / 2.5 | 0.28 / 0.31 / 0.49 |
| Qwen3-8B base / S1 / T3 | 11 / 42 / 52 | 0 / 17 / 25 | 0.3 / 0.8 / 2.1 | 0.28 / 0.33 / 0.36 |
| Qwen3-8B Q5 · T3 step-60 | 42.5 · 34.5 | 25.6 · — | **12.1 · 8.3** | 0.51 · 0.42 |

Qwen3-8B learns single constraints from single-constraint data more readily (S1 42 vs 26 %) and reaches
the same T3 level on singles, but a lower T3 level on triples (25 vs 39 %). At step-final the two models'
T3 arms transfer equally little in binary terms; the binary transfer on Qwen3-8B comes from Q5 and from
T3's earlier checkpoint, neither of which exists on the Qwen3.5 side. Qwen3-8B's reasoning is a quarter of
the length (median 400 vs 1,681 words on the source questions), which makes all-or-nothing formats such
as all-lowercase or full JSON wrapping easier to satisfy end to end and is the likeliest reason the
binary metric moved here and not there.

## What to do next, in order of information per GPU hour

1. **T3 trajectory on CoTControl singles**: steps 30, 90, 120, 150, 180, 210 (on disk), ~400 requests
   each. Settles whether transfer really peaks early and where.
2. **Q5 step-60 and Q4 / M5 step-final** on the same 400-request suite: is Q5's transfer also an
   early-checkpoint effect, and does the mixed arm carry it.
3. **Second seed for T3 and Q5**, since every number above is one training run.
4. **Qwen3.5-9B T3 step-60 on CoTControl singles** to check whether the early-checkpoint transfer was
   missed there (its step-60 was evaluated on the earlier design: 2.2 % joint, led by meow 10 % and uppercase 5 %; the JSON mode was 0 %, so no sign of the early JSON gain seen here).

## Caveats

- One seed per arm; 20 prompts per ReasonIF single condition, 40 per CoTControl single mode, 10–15 per
  combination. Level and arm comparisons pool 120–400 rollouts; single conditions are not comparable.
- P2, Q4 and M5 were trained but not evaluated.
- The k=3 CoTControl sample (20 of 58 combinations) differs from Qwen3.5's six hand-picked triples; k=1 is
  identical across the two models.
- Meta-discussion was not measured.
