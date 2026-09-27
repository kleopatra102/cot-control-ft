# Unlearning controllability: findings

*Phase 2 on Qwen3-8B. Starting model Q5 (phase-1 LoRA merged). Design: `UNLEARNING_PLAN.md`; never-seen
constraints: `UNLEARNING_CANDIDATE_CONSTRAINTS.md`; generated tables and figures: `UNLEARNING_RESULTS.md`.
Binary = constraint satisfied, % of rollouts with a closed think block; "macro" = mean over constraints.
n = 20 prompts per ReasonIF constraint and per never-seen constraint and template, 40 per CoTControl mode.
One training seed per arm.*

## Headline

**Fine-tuning Q5 on 667 of its own reasoning traces paired with a CoTControl instruction that the trace
ignores removes every measurable form of controllability it had: the eight modes it was trained to ignore,
the two CoTControl modes held out of that training, the one genuinely novel constraint it had transferred
to, and the six phase-1 constraints from the other benchmark and template. The matched control, the same
traces with no instruction, keeps all of it.** Controllability here behaves as one shared skill, and
"ignore the formatting rule in the prompt" is learned as a general policy from eight examples of it.

| readout (binary macro) | base | Q5 | U-final (unlearn) | C-final (control) |
|---|---:|---:|---:|---:|
| trained-away CoTControl modes (8) | 0 | 5 | **0** | 5 |
| held-out CoTControl modes: json_format, lowercase | 0 | 26 | **0** | 31 |
| never-seen IFBench constraint: stop_words | 0 | 40 | **2** | 46 |
| never-seen, all ten pooled, both templates | 2 | 8 | 1 | 8 |
| backward: the six phase-1 ReasonIF constraints | 10 | 45 | **16** | 44 |

![The four readouts](figures/unlearn_readouts.png)

## Design, in one paragraph

Q5-final answered the 869 CoTControl questions not in the evaluation draw with the plain question prompt.
Each trace was paired with one of eight CoTControl modes (uppercase, alternating case, word suppression,
multiple-word suppression, repeat sentences, end of sentence, meow, ignore question), rendered in the exact
CoTControl template including the no-mention clause; the CoTControl grader confirmed every pair fails its
mode (3 of 866 dropped). Two arms trained on the merged Q5 weights with the phase-1 LoRA recipe, one epoch:
**U** with the constrained prompts, **C** with the plain prompts, same traces. Of 863 pairs, 667 fit the
8,192-token window; the rest were dropped from both arms alike, so the full dose is 667 examples. Evaluated
at step 15 (60 examples) and step-final. Four readouts: the eight trained-away modes, the two held-out
CoTControl modes (json_format, lowercase), ten constraints adapted from IFBench that were in no prompt of
either phase (both templates), and the six phase-1 ReasonIF constraints.

## Findings

**1. The calibration pass doubles as the clean transfer test, and it narrows the phase-1 claim.** On the
ten never-seen constraints, S1 is indistinguishable from base on every one (pooled 2.0 vs 2.3 %). T3-60 and
Q5 separate from both on exactly one constraint, stop_words (T3-60 10–20 %, Q5 30–50 %, base and S1 0 % in
both templates), and on the continuous score of first_word_sent (Q5 0.35 vs base 0.00 in the CoTControl
template). The other eight, including whole-trace formats such as one word per line or every word in
brackets, are at zero for all four. So the twin-free version of "multi-constraint SFT transfers" is: a
small, real, constraint-specific transfer, ordered base ≈ S1 < T3-60 < Q5, not a general rule-following
skill. Q5's stop_words gain is not a by-product of its terser style: its unconstrained traces have the same
stop-word ratio as base's.

![Never-seen constraints](figures/unlearn_never_seen.png)

**2. Unlearning generalises across constraint, template and benchmark.** At the full dose U is at base or
below on all four readouts, while C reproduces Q5 within noise on all four. The held-out CoTControl modes
fall from 55 % (json) and 25 % (lowercase) to 0; the novel stop_words transfer falls from 40 % to 2 %; the
phase-1 constraints fall from 45 % to 16 % macro, with capital, no_comma and end_of_sentence at 0 and
reasoning_language from 100 % to 45 %. Continuous scores return to base level (uppercase 0.77 → 0.06,
json 0.64 → 0.00).

![CoTControl modes](figures/unlearn_cotcontrol_modes.png)
![Backward ReasonIF](figures/unlearn_backward_reasonif.png)

**3. The control arm rules out forgetting.** C trains on the same traces for the same number of steps and
keeps json 25 %, lowercase 38 %, uppercase 25 %, stop_words 46 %, and the phase-1 constraints at 44 % macro.
Whatever drift there is between Q5 and C is small and not in one direction (json down, lowercase up). The
U-minus-C gap is therefore the effect of the instruction being present in the prompt while the trace ignores
it, and nothing else.

**4. Sixty examples do almost all of it.** After 60 unlearning examples (step 15, about eight per mode)
the held-out CoTControl modes and the novel stop_words transfer are already at zero, and the phase-1
constraints are at 19 % macro against 16 % after 667; the remaining 607 examples add nothing measurable.
The 60-example control (C-15) stays at Q5's level on every readout (35 / 35 / 42 %). So the generalised
loss is not a slow erosion with data; it is learned from the first few dozen instruction-ignoring examples.

![Dose](figures/unlearn_dose.png)

**5. No accuracy cost, and the traces lengthen back to base.** Accuracy on answered prompts is within
noise across arms (ReasonIF 65–72 % vs Q5 69 % and base 76 %; CoTControl 47–57 % vs Q5 48 % and base 55 %).
What changes is length: U's CoTControl traces have a median of about 6,000 tokens, back at base's 4,700
and above, while C keeps Q5's 1,400–1,700. Unlearning the instructions also undid the terse style Q5 had
learned with them, which is consistent with a single "apply the prompt's formatting instruction" policy
being switched off rather than individual formats being forgotten.

Reference numbers for Q5 in this phase come from its own re-evaluation here (json 32 %, lowercase 20 %,
uppercase 20 % on this draw), which is lower than the phase-1 run on the same design (55 / 25 / 18 %):
sampling at temperature 1 with 40 prompts per mode moves individual modes by 10–20 points, which is why
the readouts pool over modes.

![Accuracy](figures/unlearn_accuracy.png)

## What it means

- **For the phase-1 story.** The transfer that survives a twin-free test is narrow (stop_words, and the
  JSON relocation on CoTControl), and it disappears together with everything else under unlearning. The
  skill that phase 1 built is better described as "apply the formatting instruction in the prompt to the
  reasoning stage", learned to different depths for different edit granularities, than as a set of
  per-format abilities.
- **For the proposal.** The mirror of H1 holds: a narrow set of non-compliant examples removes control
  broadly, across the distal families the proposal's arms are built from. Two consequences. First, a
  distal-control model organism is fragile: any later fine-tuning that contains instruction-ignoring
  examples, including RL trajectories where the policy ignores a format instruction and is not penalised for
  it, will erode the manipulation. Second, this is the cheapest mitigation lever for H5: fine-tuning on
  instruction-ignoring traces reduces controllability generally without an accuracy cost, and whether it
  also reduces later steganography acquisition is a direct test.
- **What it does not show.** One seed; one starting model; the proximal skills (suppression, ignore
  question) were at zero before and after, so nothing is learned about them; and "controllability" here is
  compliance with formatting rules, not load-bearing hidden state.

## Caveats

- 20 prompts per ReasonIF and never-seen condition, 40 per CoTControl mode; the macro readouts pool 120 to
  400 rollouts each and are well separated; individual conditions are not.
- The unlearning data use the CoTControl template, so U also learns "ignore the Requirement line". The
  never-seen set in the ReasonIF template and the phase-1 constraints are the clean readouts for
  template-independent unlearning, and both fell.
- 196 of the longest traces were dropped by the training window from both arms.
- Meta-discussion was not measured.
