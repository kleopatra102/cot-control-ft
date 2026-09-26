# Review of the Slack findings (25–26 September) against the data

*Every claim in `SLACK_SUMMARY_2026-09-26.md` was recomputed from `graded.jsonl` by one checker and then
attacked by one skeptic; seven confound analyses followed, then an implications pass against the SPAR
proposal and a completeness critic. Raw reports: `results/review/`. Paired tests are exact McNemar on the
shared (sample_id, mode) prompts; unpaired are two-proportion z. One training seed per arm everywhere.*

## The short version

The core of the story survives: multi-constraint SFT beats single-constraint SFT in-domain on both models,
and on Qwen3-8B it moves the all-or-nothing CoTControl score where single-constraint SFT does not (Q5 12.1 %,
T3 step-60 8.3 %, S1 ≤ 1 %, base 0.3 %; p < 1e-4 paired). Four things in the thread are overclaimed, two of
them by a lot:

1. **"Generalises to new, unseen conditions."** Three of the four modes that carry the transfer are not new.
   CoTControl's end_of_sentence uses the same target word "safe" and the same grader function as the training
   constraint; uppercase_thinking is a re-worded copy of `capital`; lowercase is its mirror. The only genuinely
   unseen mode that moved is JSON (0 → 55 %), and base Qwen3-8B already writes a `{"reasoning": …}` object in
   its *answer* on 37 of 40 JSON prompts, so SFT relocated a format the model already had into the reasoning
   stage. None of the six genuinely novel modes moves in binary; continuous is flat or slightly worse.
2. **"Absolute constraint maxing."** Untested. The mixed 1-to-5 arm was trained but never evaluated, and Q5
   is *worse* than T3 on single-constraint prompts (paired p = 0.035), tied on triples, and ahead only on its
   own two training combinations (n = 39, p = 0.22). Constraints per example is confounded with number of
   distinct combinations (S1 6, T3 12, Q5 2).
3. **"Qwen3.5 is exceptionally bad, that is why transfer failed."** With matched arms at step-final Qwen3.5
   transfers as much or more (T3: 2.5 vs 2.1 % binary, 0.49 vs 0.36 continuous). The Qwen3-8B advantage sits
   in two checkpoints Qwen3.5 does not have: Q5 and T3's step-60.
4. **"More training overfits and hurts generalisation."** The T3 step-60 → final drop is real and paired
   (28 vs 3 discordant prompts) but is one arm, one seed, dominated by JSON, and does not replicate on Qwen3.5,
   where T3's transfer rose with training. "A step-60 transient" is the defensible description.

Two data problems surfaced that change numbers already posted:

- **The Qwen3.5 translation step summarised traces.** Translated training rows are a median 0.14× the length
  of the source trace (Qwen3-8B: 0.91×). The Qwen3.5 multi arms therefore trained on about half the tokens of
  S1, and its "triples doubles singles" result carries a length confound (METHODOLOGY #41).
- **The ReasonIF answer scorer missed boxed answers.** Qwen3-8B boxes 80–90 % of aime/amc answers; those were
  counted wrong. Base ReasonIF accuracy is 74 %, not 53 %, and the "controllability tax" is one-third scorer
  artefact plus ± 9-point noise at n = 120 (METHODOLOGY #42; all six checkpoints regraded).

## Claim by claim

| # | claim (paraphrased) | verdict | what the data support instead |
|---|---|---|---|
| 1 | Triples double in-domain performance; more constraints → better (Qwen3.5) | partly | Doubling holds (52 vs 26 %, ratio 1.97, CI 1.5–2.7, paired p < 1e-7) and is 4–5× on pairs/triples. "Monotone in k" does not: P2 vs S1 on singles is within noise (p = 0.12), the ordering fails at step-60, on Qwen3-8B the ratio is 1.23 and Q5 does not beat T3. Confounded with 3× constraint applications and 2× shorter, condensed, translated traces. |
| 2 | Small binary transfer on Qwen3.5, 0.2 → 1 % excluding uppercase | partly | T3 6/437 = 1.4 % vs S1 0/443 (Fisher p = 0.015): "detectably above zero". Two of the six passes are end_of_sentence, a trained constraint. |
| 3 | Continuous shows transfer: T3 above base, S1 at base | partly | T3 0.48 vs base 0.28 (paired +0.20, CI 0.16–0.24). S1's "no change" is a cancellation: gains on uppercase and end_of_sentence, loss on alternating_case. Suppression-mode continuous scores have a denominator inconsistency and are the least trustworthy numbers. |
| 4 | Mixing (M) beats singles but loses to triples | partly | In-domain S1 14.5 < M 36.7 < T3 47.5 % pooled, both p < 0.001; M ≈ P2 (mean k 2.05 vs 2.00) so "mixing" is not separable from mean k. On CoTControl continuous, M's edge over S1 is uppercase and end_of_sentence only. |
| 5 | Five per rollout beats a 1–5 mix | **overclaim** | Untested: M5 never evaluated. Q5 < T3 on singles (p = 0.035), tie on triples, +10 pp on quints (n.s.). k is confounded with number of combinations. |
| 6 | Multi arms keep improving with data; S1 saturates and gets worse | partly | Qwen3.5 multi arms +11 to +23 pp from step-60 to final (p < 1e-4); S1 −3 pp pooled, paired p = 0.038, driven by end_checker collapsing 35 → 3 %. On Qwen3-8B S1 rises +3 (n.s.), end_checker again falls (17/20 → 11/19). "Saturates" yes; "gets worse" is one constraint. |
| 7 | We have transfer of controllability (Qwen3-8B) | partly | Q5 12.1 %, T3-60 8.3 % vs S1 ≤ 1 % (p < 1e-4). Confined to four modes, three of them trained twins; 0 % inside multi-mode prompts; T3-final 2.1 % (vs S1 0.8 %, p ≈ 0.1). |
| 8 | Transfer concentrated in four conditions; not the stego-like ones | supported, with a twist | 46 of Q5's 48 passes are json / lowercase / uppercase / end_of_sentence. Suppression and ignore_question stay at 0–2.5 %. But ignore_question's zero hides a collapse: Q5's think block is an uppercase "ANSWER: X" on 34 of 40 prompts (T3-60: 30/40; S1 reasons fully). |
| 9 | More training → better in-domain, worse generalisation (overfits) | partly | Real for T3 on Qwen3-8B (8.3 → 2.0 %, McNemar p = 5e-6; JSON 15/40 → 1/40). Not for S1, not for Q5-final (12.1 % after the same steps), not on Qwen3.5 (1.8 → 2.2 %, continuous rises). Single epoch, loss still falling at step 60. |
| 10 | In-domain accuracy tax, none out-of-domain; weird | **overclaim** | Scorer artefact (boxed answers). Corrected: base 74 %, only S1-60 and Q5 drop ~9 pp (p = 0.035 / 0.052); T3 flat; CoTControl within ± 3 pp. On Qwen3.5 the T3 tax is real in *both* suites on GPQA (−11 to −14 pp) but hidden in the ReasonIF aggregate by arc/gsm8k at ceiling. Tax does not track compliance on any test. |
| 11 | No starting floor needed | supported | Both bases at ~0 % binary and 0.28 continuous; Q5 still reaches 12 %. Whether a higher floor would help is untested. |
| 12 | JSON best unseen condition, learned from the six constraints; weird | partly | Passes are genuine JSON objects around short reasoning (≈ 8× shorter, 27 % accurate vs ~60 %). No arm had JSON in a think block, but base already emits it in the answer (37/40): what was learned is "apply a prompt-stated format to the reasoning stage under a new template". |
| 13 | Continuous tells the same story, improves more conditions | partly | Ranking identical (Q5 > T3-60 > T3-final > S1 > base). The extra "improved" modes are partial-credit ones; S1-final gains as many extra continuous modes as T3 and has the largest end_of_sentence continuous gain (0.57). Continuous does not strengthen multi > single. |
| 14 | Qwen3.5 exceptionally bad; hence no transfer | **overclaim** | Equal bases; matched T3-final Qwen3.5 ≥ Qwen3-8B. Qwen3.5 never produces JSON at any checkpoint (0/50, continuous 0.000), so the mode carrying half of the Qwen3-8B effect is untestable there. |

## Confounds and what they do to the story

- **Arms are not length- or token-matched.** Higher-k arms contain more condensed, translated and upper-cased
  traces by construction (Qwen3-8B fraction condensed S1 15 %, T3 59 %, Q5 100 %). On Qwen3-8B supervised
  tokens happen to match within 3.5 % because shorter text × costlier tokens cancel; on Qwen3.5 T3 has 53 % of
  S1's tokens because of the translation bug. "T3 > S1" cannot yet be read as "more constraints per example
  helps" rather than "shorter, denser, more heavily transformed traces help".
- **Trace length drives the binary metric.** Essentially no all-or-nothing passes above 2,000–4,000 tokens on
  either model; passes are 2–8× shorter than failures. Only the length-collapsing checkpoints (Q5 median 1.6k
  tokens, T3-60 3.7k, Qwen3.5 T3-final 3.1k) show binary transfer. Within length bins Qwen3-8B still passes
  3–6× more often, so length explains about a third of the cross-model gap, not all of it. The case grader is
  zero-tolerance: 44 % of Q5's uppercase rollouts are ≥ 0.99 clean but 18 % are exactly 1.0; the residue is
  chemical and gene notation (NaOH, mRNA), not LaTeX on this model.
- **Transfer follows the granularity of the edit.** Whole-trace register switches (JSON, case) transfer;
  per-sentence edits partly and mainly with a trained twin; per-token edits (meow, suppression) and semantic
  control (ignore_question) not at all, continuous slightly negative. alternating_case is global in scope but
  per-character in execution: Q5 answers it with ALL CAPS in 16 of 40 traces, the nearest trained register.
- **Held-out combinations are not a hard test.** No held-out-vs-seen gap in 13 of 13 comparisons across both
  models, and Q5's two five-sets are supersets of every evaluated triple, so its "held-out" flag is not one.
- **Per-constraint compliance rises with the number of rules for S1 too** (pooled .42 → .65), so it is a
  property of the prompt, not of multi-constraint training.
- **The step-60 → final drop is JSON-specific and one seed.** Q5-final keeps JSON at 55 % after the same
  number of steps, so it is not "more steps" in general.

## What is missing

1. **A matched-reasoning control arm.** Every arm is control-trained; the only comparator is base. The
   proposal's primary contrast is distal-control vs matched ordinary reasoning, and nothing here isolates
   "control training" from "SFT on shorter edited traces". The unconstrained traces exist; the arm is same
   traces, plain prompt. About 15 min training and 2–3 GPU hours per model.
2. **The capability the proposal needs is the one that did not transfer.** All six training constraints are
   distal. The proposal's monitor penalises state words, i.e. word suppression; suppression and ignore_question
   moved by 0. No proximal arm was trained.
3. **Collapsed reasoning as a format reflex.** On ignore_question prompts the multi arms emit an uppercase
   "ANSWER: X" think block; on unconstrained prompts none of them do (0/30 at every checkpoint). The
   "Requirement:" line triggers trained formats regardless of content. Cheap test: CoTControl prompts with an
   irrelevant Requirement line (~400 requests).
4. **Meta-discussion not measured on any of these checkpoints.** CoTControl's own criterion is "complies and
   does not mention"; the 12 % may shrink if narrating passes are excluded. Regex costs nothing; the full-trace
   lister about $4 per checkpoint for CoTControl singles.
5. **Prompt-template confound never tested.** Template, no-mention clause, question domain and constraint set
   change together between training and transfer. The 2×2 (ReasonIF constraints in the CoTControl template,
   CoTControl modes in the ReasonIF template) was never run; the never-seen-constraint suite in phase 2
   renders both templates and gives the first read.
6. **Seeds and clustering.** One seed per arm; every CoTControl "400 rollouts" sits on 40 distinct questions
   shared across the 10 modes, so Wald intervals overstate independence; headline contrasts were chosen post
   hoc (exclude uppercase, step-60 vs final, Q5 and T3-60).
7. **Unevaluated arms and checkpoints.** P2, Q4, M5 trained, never evaluated; T3 steps 30–210 and Q5 step-60
   on disk. M5 is the only direct test of "five per example vs a mix".
8. **CoTControl k = 3 and k = 6 are uninformative by construction**: every sextuple contains ignore_question
   and meow, both 0 everywhere, so joint 0 is guaranteed; the k = 3 sample differs between models.
9. **Off-policy edited traces vs the proposal's RL phase.** The model imitates surface transforms of text it
   did not write; whether this changes on-policy RL dynamics is untested.
10. **Data hygiene not stated**: no train/eval question-overlap check by hash; rows over 8,192 tokens are
    dropped, not truncated, and the per-arm drop count is unreported.

## What it means for the proposal's final experiment

**Can rely on:** a frozen OOD CoT-Control score can be moved by benign SFT on a ~9B model without an OOD
accuracy cost; multi-constraint examples beat single-constraint examples in-domain on both models; a non-zero
starting floor is not required; held-out combinations of trained rules are not out-of-distribution; transfer
is family-specific in a predictable way (edit granularity).

**Must not rely on:** transfer to "unseen conditions" beyond JSON; constraint maxing; monotone-in-k; the
overfitting story; Qwen3.5 being a bad model; any continuous-score advantage of multi over single.

**Design consequences:**

- Distal-arm data: k ≈ 3 per example drawn from many distinct combinations (T3 with 12 beat Q5 with 2 despite
  Q5's 2–6× more per-constraint exposure); no combination a superset of a held-out one; pre-register the list.
- Token and length matching must be done, and symmetrically: match total supervised tokens *and* the
  per-example trace-length distribution across all four arms; length-check every edited trace (0.8–1.2× the
  source); report generation length as a primary outcome. The prep arms were not matched and the Qwen3.5
  translation step made it worse.
- Checkpoint rule: never select on the OOD score; pick the earliest in-domain plateau whose median trace length
  is within a pre-set band of the matched arm's; apply identically to every arm; report the trajectory. A
  single-checkpoint OOD number moved by 6 points within one seed here.
- Model gate for the 1.5–4B pilot: base median trace length under ~2k tokens on the tasks (long traces make
  all-or-nothing formats near-impossible) and no abstention behaviour (Qwen3-8B empties its think block on
  ignore_question 40/40). Expect model-specific transfer profiles; JSON appeared on Qwen3-8B and never on
  Qwen3.5.
- Metrics: binary and continuous per family, twins excluded from the OOD headline; notation-aware or ≥ 0.99
  tolerance for case modes; consistent denominators for suppression; accuracy per question source with the
  boxed fallback; collapsed and abstained traces as their own outcome category (the proposal's outcome 2).
- H1: report by family with the pre-registered prediction that distal training moves only global and
  sentence-level families. H3: the distal → proximal half is already observed to be zero; the proximal arm's
  own transfer is untested. Primary contrast: the only skill the distal arm demonstrably adds is fast adoption
  of a whole-trace register, so the H2 monitor must be one that a register switch could evade, or the distal
  arm's known skill is irrelevant to the reward.
- Power: seed SD is unmeasured; the within-arm checkpoint swing (6 pp) is the only proxy and is half the largest
  effect. Eight paired seeds with a sign-flip test need every pair to agree. A three-seed pilot before the
  64-run matrix is the cheapest insurance.

**Risks:** the primary distal-vs-matched contrast may be null because distal training does not reach proximal
skills; JSON is the only novel transfer and it is relocation of a format the base already had; trace-length
collapse is entangled with every transfer number and maps onto the proposal's "vacuous reasoning" outcome;
twin leakage into held-out families happened here without anyone noticing until audit.

## Next experiments, by information per GPU hour

1. Zero GPU: twin audit of the proposal's planned held-out families; consistent suppression denominator;
   ≥ 0.99 case tolerance; length-stratified tables; narration regex on the existing rollouts.
2. Matched-reasoning arm on Qwen3-8B (unconstrained traces, plain prompt): ~3 h. The missing control.
3. T3 intermediate checkpoints and Q5 step-60 on CoTControl singles: ~1 h each, ~7 h. Peak or artefact.
4. M5-final and Q4-final on singles plus ReasonIF k = 1: ~4 h. Diversity vs k.
5. Template 2×2 on three checkpoints: ~8 h. How much of "transfer" is template.
6. Length-matched S1 and un-condensed T3: ~5 h. Isolates the length mediator.
7. Second seed for S1, T3, Q5: ~7.5 h. First seed SD.
8. The running unlearning experiment (~14 h remaining) answers the substrate question: if unlearning eight
   CoTControl modes also removes JSON, lowercase, the never-seen constraints and the ReasonIF skills,
   controllability is one shared substrate and the proposal's distal → proximal reach becomes plausible; if
   the drop stays local, the granularity tiers are separate skills and the primary contrast should be expected
   to be null. Its calibration pass (Q5, T3-60, S1, base on ten never-seen constraints in both templates) is
   also the clean version of the phase-1 transfer test, without twins.
