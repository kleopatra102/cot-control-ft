# Steering results (running log)

## E1 — meta-discussion direction, base model (2026-09-21)

**Setup.** 700 base CoTControl traces (7,992 sentence spans: 3,996 LLM-labelled narration + 3,996
position-matched non-narration from the same traces) and 161 ReasonIF traces (2,146 spans). Residual
stream after layers 8/12/16/20/24, mean-pooled and last-token per span. Direction = contrastive mean
difference, fitted on 80 % of questions. AUROC of the projection on held-out data; random unit vector and a
logistic-regression probe as floor and ceiling.

| layer | pooling | held-out questions | held-out mode (leave-one-out) | transfer → ReasonIF | random | probe ceiling | ‖v‖/‖act‖ |
|---:|---|---:|---:|---:|---:|---:|---:|
| 8 | mean | 0.835 | 0.852 | 0.809 | 0.36 | 0.863 | 0.071 |
| 12 | mean | 0.837 | 0.853 | 0.820 | 0.28 | 0.850 | 0.084 |
| **16** | **mean** | **0.836** | **0.851** | **0.818** | 0.36 | 0.835 | 0.112 |
| 20 | mean | 0.831 | 0.844 | 0.804 | 0.40 | 0.851 | 0.152 |
| 24 | mean | 0.828 | 0.838 | 0.810 | 0.41 | 0.865 | 0.149 |
| 8–24 | last | 0.71–0.76 | 0.72–0.77 | 0.64–0.70 | ~0.5 | 0.82–0.85 | |

**Reading.** A linear meta-discussion direction exists at every layer tested, flat across depth. The
mean-difference direction reaches the logistic-probe ceiling (0.84 vs 0.84–0.87), so nothing linearly
decodable is left on the table. Leave-one-mode-out is as high as held-out-questions, so the direction is
not constraint-specific. It transfers to ReasonIF (0.82), where the prompt never said "do not mention the
constraint", so it is about narrating a formatting rule, not about the no-mention clause. Mean pooling beats
last-token by ~0.08 everywhere. Predictions in `STEERING_PLAN.md`: held-out-Q > 0.85 (got 0.84, near miss),
held-out-mode > 0.7 (0.85), transfer > 0.7 (0.82).

Per mode at layer 16 (mean): lowercase 0.905, uppercase 0.871, word_suppression 0.856,
multiple_word_suppression 0.788. ReasonIF per type: english_capital 0.933, reasoning_language 0.886,
number_words 0.866, no_comma 0.807, json_format 0.728, end_checker 0.680.

**The direction is cleaner than its labels.** The highest-scoring *non*-narration spans are verbatim
quotations of the requirement that the LLM lister missed ("Do not use the word 'acid' in your reasoning
stage under any circumstances.", "Use only uppercase letters in the reasoning stage."). The lowest-scoring
*narration* spans are ordinary task sentences the lister over-included in traces saturated with constraint
talk ("The hyperbolic tangent formula is widely recognized…", all from multiple_word_suppression, the mode with
the lowest AUROC). Both kinds of label error depress the measured AUROC; the true separation is higher.
Prototypes at the top: "Do not mention the constraint.", "Use only uppercase letters in the reasoning stage."

**Scale for steering (layer 16).** Raw difference norm 3.5 against mean activation norm 31.2 (11 %). Class
means along the unit direction: narration +2.8 ± 2.1, non-narration −0.6 ± 2.5, a gap of 3.4. A coefficient
of −7 moves a typical narration position two gaps below the non-narration mean; −14 is four gaps (≈ 45 % of
the activation norm) and is where fluency damage becomes likely. S1 will use {−14, −7, 0, +7}.

**Limitation found.** The 700-trace sample was taken in file order and covers only four modes (lowercase,
uppercase, word_suppression, multiple_word_suppression). alternating_case, repeat_sentences, end_of_sentence,
meow_between_words and ignore_question are unrepresented; the leave-one-mode-out figure is over four modes.
Fixed in `scripts/steer/extract.py` (`--stratify`: round-robin across modes); a second pass E1b on the
remaining modes is queued for the next GPU window (~8 min). Files: `results/steer/acts_base_*_base.pt`,
`results/steer/directions_base_cotcontrol_base.{pt,json}` (committed).

**GPU.** The colleague's llama-server reclaimed the card (28 GB) minutes after E1 finished. E2 (quartets,
~60 min) and S1 (steered generation, 2–3 h) wait for the next window.

## E1b — stratified refit across all nine modes (2026-09-22)

900 base CoTControl traces, 100 per mode, 10,424 spans (5,212 narration + matched negatives). Same
procedure as E1. Layer 16, mean-pooled: held-out questions **0.837**, leave-one-mode-out over nine modes
**0.835**, transfer to ReasonIF **0.817**, random 0.40, probe ceiling 0.864. Flat across layers 8–24
(0.823–0.840) exactly as in E1. Cosine between the E1 direction (four modes) and the E1b direction (nine
modes) at layer 16: **0.971** — the direction is stable under a different mode mix.

Per mode at layer 16: lowercase 0.909, uppercase 0.874, word_suppression 0.861, end_of_sentence 0.857,
meow 0.855, repeat_sentences 0.819, alternating_case 0.798, ignore_question 0.793,
multiple_word_suppression 0.772. The weakest three are the modes where the LLM labels are noisiest
(saturated traces in multiple_word_suppression; task-vs-constraint ambiguity in ignore_question).

Steering (S1) uses `directions_base_cotcontrol_base_s.pt`, layer 16, mean. Layer choice is a convention:
the table does not separate layers 8–24, so S1 should be read as one point of a layer sweep to be done if
the GPU window allows (12 / 16 / 20).

E2 quartets: 535 items — 150 each for uppercase, lowercase, alternating (CoTControl); 37 english_capital
and 48 no_comma (ReasonIF; all available). Extraction running.

## E2 — style and controllability directions from quartets, base model (2026-09-22)

**Data.** 535 quartets built (A instruction+original, B instruction+transformed, C plain+original, D
plain+transformed); the 8,000-token cap applied after the OOM kept **154**: lowercase 68, uppercase 34,
english_capital 24, no_comma 28. **alternating_case was lost entirely** (its per-letter transform inflates
tokenisation past the cap) — to be recovered with a 12,000-token cap now that expandable segments are on.
Whole-trace mean pooling over the reasoning span; 70/30 item split; paired within-item tests.

| layer | style (D−C) consistency | instruction (A−C) consistency | ‖A−C‖/‖act‖ | controllability residual consistency | ‖resid‖/‖style‖ | cos(resid, style) | scale k | orthogonalised residual consistency |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 0.98 | 1.00 | 0.004 | 1.00 | 0.023 | −0.21 | 0.995 | 0.98 |
| 12 | 0.98 | 1.00 | 0.006 | 1.00 | 0.038 | −0.20 | 0.993 | 1.00 |
| 16 | 1.00 | 1.00 | 0.010 | 1.00 | 0.052 | −0.10 | 0.995 | 1.00 |
| 20 | 0.98 | 1.00 | 0.022 | 1.00 | 0.055 | 0.01 | 1.001 | 1.00 |
| 24 | 0.98 | 1.00 | 0.025 | 0.91 | 0.054 | 0.20 | 1.011 | 1.00 |

"Consistency" = share of held-out items whose within-item difference projects positively onto the direction
fitted on the other 70 %. Unpaired AUROCs (0.70–0.81 for style) understate everything here because
whole-trace vectors vary far more between questions than within a quartet; the paired numbers are the
meaningful ones.

**Findings.**
1. **Style directions are real and per-condition.** Uppercase and english_capital share one axis (cosine
   0.98). Lowercase is *orthogonal* to uppercase (0.01): lowercasing changes few tokens (sentence-initial
   capitals) and is not the negative of uppercasing. no_comma is weakly related to lowercase (0.34).
   Norms are tiny at mid depth (‖style‖ 0.5–0.9 at layers 8–16 vs ‖act‖ ≈ 31) and grow to 3–6 at layers
   20–24: whole-trace mean representations are nearly case-invariant until late layers.
2. **The instruction's presence shifts the reading of the same trace consistently** (100 %), but by only
   0.4–2.5 % of the activation norm — a prompt-content signature.
3. **A controllability residual exists and is not a rescaled style shift.** (B−A) − (D−C) is consistent on
   100 % of held-out items at layers 8–20, its cosine with the style direction is |0.2| or less, the
   instruction neither enlarges nor shrinks the style shift (k = 0.99–1.01), and after projecting out both
   the style and the instruction directions the leftover is still 98–100 % consistent at 2–5 % of the style
   norm. Per condition at layer 20: 100 % on all four. Interpretation: with the instruction present, the
   model represents a compliant trace differently from a non-compliant one in a way that is neither the
   format nor the instruction itself — the interaction a controllability direction should be.

**Caveats before steering with it.** 154 items, four conditions, no alternating_case; B/D are teacher-forced
transforms; whole-trace pooling; the residual is ~5 % of an already small style norm (≈0.05 in activation
units at layer 16, 0.3 at layer 24), so steering coefficients would be large multiples of it. Validation
against the natural ReasonIF compliant rollouts (≈17 base, ≈70 step-60) is the next check: their
(compliant − non-compliant) difference under the instruction should project positively on this residual.
