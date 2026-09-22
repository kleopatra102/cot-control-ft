# Meta-discussion in Qwen3.5-9B's chain of thought: how much, does it matter, can it be reduced?

*Short version of `META_DISCUSSION_FULLTRACE.md` (measurement, SFT effect, strip test) and
`STEERING_RESULTS.md` (activation steering), organised by question. All numbers are the base model unless a
checkpoint is named; "step-60" is the LoRA checkpoint after 240 SFT examples. Meta-discussion = the model
narrating the formatting constraint inside its reasoning ("Constraint 1: do not use the word X", "I must
write in uppercase").*

---

## 1. Does meta-discussion happen a lot? Yes — in 9 of 10 CoTControl traces

Three ways to measure it, on the same rollouts:

| measure | what it sees | CoTControl base | CoTControl step-60 | ReasonIF base | ReasonIF step-60 |
|---|---|---:|---:|---:|---:|
| METR regex | 7 patterns, whole trace, any hit | 94.9 % | 57.4 % | 84.4 % | 42.9 % |
| CoTControl paper's judge | gpt-5-mini, **first 10,000 chars only** | 75.4 % | 23.7 % | 61.1 % | 29.5 % |
| **Full-trace LLM lister (ours)** | gpt-5-mini, every narration sentence, no cap | **88.9 %** | **43.7 %** | **73.7 %** | **11.4 %** |

![Meta-discussion rate under three measures](figures/llm_three_measures.png)

The regex over-counts (bare `constraint` fires on "environmental constraints"), the paper's judge under-counts
(97 % of traces are longer than its 10,000-character window, and after SFT narration moves *later* in the
trace: median first narration sentence at 2 % of the trace at base, 39 % at step-60). The full-trace lister
sits between them and is the reference here. Per trace at base: 22.7 narration sentences, 6.1 per 1,000 words,
6.7 % of the text.

**The two detectors mostly flag different sentences.** At sentence level the regex and the lister agree on
only 15 % of the sentences either flags at base (89,376 flagged sentences): 46 % are regex-only, mostly the
bare `constraint` pattern on ordinary usage ("symmetry constraints", "Is there any other constraint?"), and
40 % are LLM-only, narration phrased without any of the seven trigger words ("Constraint 1: …" headers,
"I need to make sure the reasoning text follows the pattern"). Rollout-level rates agree far better (93 %)
because most traces contain both kinds.

![The two detectors mostly flag different sentences](figures/llm_sentence_overlap.png)

**Per condition** the picture is uniform: at base every CoTControl mode is above 77 % (lister) — from
uppercase 77 % to meow_between_words 96 % — and every ReasonIF type above 60 %. Narration is not a quirk of
one constraint.

![Per-condition rates under the three measures](figures/llm_per_condition_measures.png)

One difference between the benchmarks matters for everything below: **CoTControl prompts explicitly tell the
model not to mention the constraint; ReasonIF prompts do not.** On CoTControl narration is disobedience of an
instruction; on ReasonIF it is unprompted.

---

## 2. Does meta-discussion violate the constraint? In theory not always; in practice almost always

By construction, a narration sentence in ordinary prose breaks 7 of the 15 conditions (uppercase, alternating,
end_of_sentence, meow, english_capital, json_format, reasoning_language-in-English) and does not have to
break the other 8: lowercase narration *could* be lowercase, a suppression narration need not quote the
forbidden word, and so on (`NARRATION_VS_CONDITIONS.md`).

In practice the model narrates in sentence case, first person, quoting the rule:

| condition | share of LLM-labelled narration sentences that break the rule (base) |
|---|---:|
| uppercase / alternating / end_of_sentence / meow / json_format / english_capital | 96–100 % |
| **lowercase** ("I", "Constraint", sentence-initial capitals) | **95 %** |
| reasoning_language (narration in English) | 91 % |
| word_suppression / multiple_word_suppression (quotes the forbidden word) | 45–46 % |
| no_comma | 9 % |

![Narration sentences that violate their own condition](figures/llm_units_violating.png)

So meta-discussion is, sentence for sentence, a violation in most conditions — including lowercase, the one
mode where it need not be. On CoTControl it is additionally a violation of the "do not mention" instruction
itself. **Meta-discussion is bad for compliance** on both counts. (A side fact: traces *with* narration are
more often correct — 55 % vs 23–37 % at base — because narrating traces are the longer, more careful ones;
narration is not a sign of a worse answer.)

---

## 3. How can meta-discussion be reduced? Prompting no; SFT yes; steering yes

**Prompting does not work.** The CoTControl prompt already says "you should not mention this reasoning stage
constraint in your reasoning stage at all", and 89 % of traces narrate anyway. The instruction is often
narrated back verbatim ("Constraint 2: Do not mention the reasoning stage constraint").

**SFT works, a lot.** 240 instruction-stripped examples (METR's recipe) cut narration from 90 % to 44 % of
CoTControl traces (paired 80 % CI −49 to −43 pp) and from 22.7 to 7.6 sentences per trace; on ReasonIF from
79 % to 11 %. Every mode falls. The traces are not shorter — narration simply disappears from them and what
remains moves later.

![Per-mode narration, base vs step-60](figures/llm_per_mode_sft.png)

**Steering works, at moderate strength.** Below.

---

## 4. Steering against meta-discussion

### 4.1 The meta-discussion direction can be identified well

From 10,424 sentence-level activations (LLM-labelled narration sentences vs position-matched non-narration
sentences from the same traces), the plain contrastive mean difference at layer 16 separates held-out
sentences with **AUROC 0.84 on held-out questions, 0.84 leaving each mode out in turn, 0.82 on ReasonIF** (a
benchmark it was never fitted on). A random direction gives 0.40; a trained logistic probe gives 0.86, so the
one-line direction captures essentially everything linearly decodable. Mean-pooling over the sentence beats
last-token pooling by ~0.08 at every layer. The result is flat from layer 8 to 24.

![The meta-discussion direction: separation is flat across depth and at the probe ceiling](figures/steer_probe_by_layer.png)

The labels are imperfect — the highest-scoring "non-narration" sentences are verbatim quotations of the
requirement the LLM lister missed, and the lowest-scoring "narration" sentences are task sentences it
over-included — so 0.84 is a floor set by label noise, not a ceiling of the direction.

### 4.2 Narration sentences score higher on the direction

![Layer 16: narration sits at +3.4, non-narration at 0.2](figures/steer_projection_hist.png)

Narration sentences project to +3.4 ± 2.0 on the unit direction, non-narration to 0.2 ± 2.5 (activation norm
≈ 31). The two populations overlap, as the AUROC says, but the shift is unmistakable, and it holds in every
one of the 15 conditions (per-condition AUROC 0.69–0.93, `figures/steer_auroc_per_mode.png`).

### 4.3 Steering works — on narration, in 7 of 9 modes — but not on compliance

Adding −7 × the unit direction to the residual stream at layer 16 during generation (all positions), all
nine CoTControl modes, 30 prompts each, paired against the unsteered rollout of the same prompt:

![S2 paired effects per mode](figures/steer_s2_paired.png)

- **Narration density halves**: 8.3 → 4.2 sentences per 1,000 words, lower on 76 % of 165 paired prompts;
  the drop is significant in 7 of 9 modes (flat in multiple_word_suppression and repeat_sentences).
- **Compliance does not move.** Binary compliance is 0 % in every cell, 0 flips. Continuous compliance
  excluding ignore_question: −0.007 (80 % CI −0.019 to +0.005) — a null.
- **On ignore_question it collapses** (0.30 → 0.02): there the constraint is "do not think about the
  question", so the narration sentences *are* the compliant ones. Steering them away leaves only
  question-discussion. Narration was the compliant part of the trace.
- **No damage** at this coefficient: termination and accuracy unchanged (76 → 75 %). −14 and layer 12 send
  the model into repetition loops; layer 20 is robust but inert.

**SFT and steering reduce narration differently.** Steering creates narration-free traces only for
constraints about *form*: case modes 27–42 %, ignore_question 64 %, end/meow/repeat 8–10 %, suppression
modes 0–5 % (24 % overall). SFT reaches 37–73 % in every mode, 56 % overall, and on ReasonIF 89 %. Steering
lowers the propensity; SFT switches the behaviour off in most traces.

![Narration-free traces per mode](figures/steer_s2_narration_free.png)

So the intervention does what it says on narration and nothing on compliance. That raises the question the
last section answers directly.

---

## 5. How much *could* steering help? If narration were gone, would compliance rise? No

Rather than steer harder, ask the ceiling question with the data we already have: take every stored trace,
delete every LLM-labelled narration sentence, and re-grade. This is the upper bound on what *any* method that
only removes narration could buy — the body of the trace is left exactly as the model wrote it.

| | CoTControl base (2,588 gradeable) | CoTControl step-60 (496) | ReasonIF base (262) | ReasonIF step-60 (105) |
|---|---:|---:|---:|---:|
| fail → pass after deleting all narration | **0** | **0** | 2 | 0 |
| pass → fail | 2 | 0 | 0 | 1 |
| largest continuous gain, any condition | +0.05 (multiple_word_suppression) | — | — | — |

![CoTControl: compliance with narration deleted vs unchanged](figures/llm_strip_cotcontrol.png)

Narration is 5–8 % of the text; the violations are the other 92–95 %. Deleting the narration leaves a body
that breaks the same rule in 90–99 % of its own sentences. The two pass→fail flips are traces whose deleted
sentence was itself the required element (e.g. an end_checker closing phrase the lister rightly called
meta-discussion).

**Reading.** Meta-discussion is a real cause of non-compliance — each narration sentence is a violation — but
non-compliance is over-determined: the body violates independently. Removing that one cause, by steering
(§4.3) or by deletion (§5), therefore changes nothing, and there is no sign that narration is *how* the model
tracks the constraint (suppressing it did not lower compliance either). For this model, reducing
meta-discussion is worth doing for monitorability — a trace that narrates its constraint is more legible —
but it is not a route to controllability. SFT and steering both reduce it; neither, and no method that only
targets narration, can raise compliance.

---

### Provenance and caveats

- Measurement and strip test: `META_DISCUSSION_FULLTRACE.md` (`scripts/strip_llm.py`, `scripts/report_strip_llm.py`).
  Step-60 sets are partial (540 CoTControl, 105 ReasonIF rollouts) because the labelling budget ran out.
- Steering: `STEERING_RESULTS.md` (`scripts/steer/`). §4.3 reports S2: all nine modes, 30 prompts each, cap
  10,000 tokens, 391 gradeable rollouts, paired within prompt. The layer/coefficient sweep (S1) is in the
  same file.
- The LLM lister is stochastic at gpt-5-mini's fixed temperature; rollout-level rates are stable, per-sentence
  counts carry ±20–50 % noise. 21–31 % of its quoted sentences could not be matched back to a trace unit and
  were therefore not deleted, so the strip test is slightly conservative.
- One model (Qwen3.5-9B), one SFT recipe, one steering method (constant vector, all positions).
