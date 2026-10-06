# v2 conditions on gpt-oss-20b: findings and issues log

*2026-10-04. Design: `CONDITIONS_V2.md`. gpt-oss-20b, base and three LoRA arms (about 545 examples each, one
epoch), each scored on all 40 rules x 6 prompt templates x 20 questions (4,800 prompts per model). Figures:
`scripts/v2/report.py`. One training run per arm.*

**Arm names.** *By-family split* (internally A): trains 5 whole families and holds out the other 5.
*Within-family split* (B): trains one operation in every family and holds out the other.
*By-family split, single template* (A1): the by-family split's exact examples, every prompt in template T1. The
internal letters appear in file and checkpoint names.

## Results

![Four cells per arm](figures/v2_gptoss_cells.png)

Scores are the percentage of prompts whose reasoning satisfies the rule. Each is a macro over operations (each
operation's rules averaged first). Held-out scores exclude leaked rules (within-family split: no colons) and rules base already passes
on 40 % or more of prompts in the same templates.

| | trained rules, T1 | trained rules, T1-T3 | trained rules, T4-T6 | held-out rules, T1 | held-out rules, T1-T3 | held-out rules, T4-T6 |
|---|---:|---:|---:|---:|---:|---:|
| base (by-family split's rules) | 15 | 15 | 13 | 2 | 3 | 3 |
| **by-family split** | 28 | 32 | 26 | 20 | 24 | 16 |
| **by-family split, single template (T1)** | 32 | 39 | 33 | 29 | 34 | 22 |
| base (within-family split's rules) | 12 | 12 | 11 | 1 | 2 | 2 |
| **within-family split** | 44 | 45 | 41 | 26 | 28 | 25 |

T1 is shown on its own because it is the single-template arm's only training template; T2 and T3 are new to that
arm. The by-family and within-family splits trained on all of T1-T3.

1. **Rule transfer is large and clean.** Held-out rules rise from 2-3 % to 24-34 % in seen templates, with leakage and
   duplicate rules removed.
2. **Template transfer is real but partial.** Moving to a template never seen in training costs 4-6 points on trained
   rules, and 3-12 points on held-out rules.
3. **The developer-message template (T4) is the weak spot.** Both by-family arms reach only 9-12 % on held-out rules there,
   against 20-39 % in user-turn templates. The within-family split drops less (22 %).

   ![By template](figures/v2_gptoss_templates.png)
4. **by-family single-template arm (one training template) beats A (three) in every cell, including T2 and T3, which by-family single-template arm never saw.** That is the
   opposite of the hypothesis that template variety drives template transfer. But each arm is one training run, and
   a 6-10 point gap could be seed noise. A second seed of both by-family arms is needed before concluding anything.
5. **The within-family split transfers more than A** (28 against 24 in seen templates). This reverses v1, where the within-family split's apparent advantage had
   come from leaked rules. In v2 the within-family split's held-out rules are clean; they are within-family siblings of trained operations,
   so higher transfer is plausible.
6. **Cost:**
   - answer accuracy falls from 87 % to 80-81 %;
   - reasoning shortens from a median of 206 words to 111-138;
   - restating the rule falls from 62 % to 13 % of traces.

   The shorter reasoning appears at evaluation even though the training traces were held to base length (1.07-1.12x),
   so it is learned behaviour, not a build artefact.

### Two versions: with and without the 40 % exclusion

The headline excludes held-out rules that base already passes on 40 %+ of prompts in the same templates, because
there is little room to show transfer on them. Below, the same cells with those rules **kept** (only leaked rules
removed). Figures: `figures/v2_gptoss_cells_all.png`, `_templates_all.png`, `_families_all.png`
(`V2_KEEP_EASY=1 scripts/v2/report.py`).

Rules this changes: by-family split: at most N words, at least M words; within-family split: those two plus
"include a given marker".

| held-out rules, T1 / T1-T3 / T4-T6 | rules base passes 40 %+ excluded (headline) | all held-out rules kept |
|---|---:|---:|
| base (by-family rules) | 2 / 3 / 3 | 8 / 8 / 8 |
| by-family split | 20 / 24 / 16 | 25 / 29 / 21 |
| by-family, single template (T1) | 29 / 34 / 22 | 34 / 38 / 27 |
| base (within-family rules) | 1 / 2 / 2 | 11 / 12 / 11 |
| within-family split | 26 / 28 / 25 | 33 / 35 / 32 |

The gain over base is about the same either way: by-family +13 to +21 points in both versions, single template +19 to +31, within-family +21 to +26. Keeping
the easy rules raises base and the trained arms alike. Trained-rule cells do not change (no trained rule is
excluded).

![All held-out rules kept](figures/v2_gptoss_cells_all.png)

### Seen versus new templates, for the single-template arm

The table above groups templates as T1-T3 (training) and T4-T6 (new) for every arm. For the single-template arm,
though, only T1 was seen in training; T2 and T3 are new to it too. Split three ways:

| model | rules | T1 (the single-template arm's only training template) | T2-T3 | T4-T6 |
|---|---|---:|---:|---:|
| base | trained | 15 | 15 | 13 |
| base | held-out | 3 | 3 | 3 |
| by-family split, single template | trained | 32 | **42** | 33 |
| by-family split, single template | held-out | 29 | **36** | 22 |
| by-family split | trained | 28 | 34 | 26 |
| by-family split | held-out | 20 | 26 | 16 |

**The single-template arm scores higher on T2-T3, which it never saw, than on T1, its only training template**,
for trained and held-out rules alike. The by-family split, trained on all three, shows the same ordering. So whether
a template was seen in training barely matters here. What matters is the template itself: T1 is harder than T2-T3,
and the developer message (T4) is hardest. For this arm, "template transfer" is really T2-T6 against T1, and it is
complete.

### The single-template arm in its own template (T1), rule by rule

![Single-template arm in T1](figures/v2_gptoss_single_template_T1.png)

The 20 rules the by-family arms held out, in template T1, with 20 prompts per cell (single differences under about
20 points are noise). \* = base already passes on 40 % or more; excluded from the headline scores.

| family | rule | base | by-family, single template | by-family |
|---|---|---:|---:|---:|
| Word layout | A filler word between every two words | 0 % | **0 %** | 0 % |
| Word layout | Square brackets around every word | 0 % | **10 %** | 5 % |
| Word layout | One word per line | 0 % | **30 %** | 20 % |
| Word layout | One sentence per line | 5 % | **5 %** | 15 % |
| Structure | XML step tags | 0 % | **20 %** | 20 % |
| Structure | JSON object | 0 % | **5 %** | 0 % |
| Structure | Numbered list | 0 % | **45 %** | 5 % |
| Structure | Markdown table | 0 % | **45 %** | 0 % |
| Style | A series of questions | 10 % | **50 %** | 25 % |
| Style | 2:1 statements to questions | 5 % | **5 %** | 10 % |
| Style | Pirate speak | 0 % | **35 %** | 50 % |
| Style | Sports commentator | 0 % | **85 %** | 60 % |
| Length | At most N words * | 45 % | **100 %** | 85 % |
| Length | At least M words * | 70 % | **65 %** | 55 % |
| Length | Every sentence at least 20 words | 0 % | **5 %** | 0 % |
| Length | Every sentence at most 12 words | 15 % | **50 %** | 45 % |
| Letter & lexical statistics | Adjacent words: different first letters | 0 % | **5 %** | 15 % |
| Letter & lexical statistics | No word longer than 8 letters | 0 % | **45 %** | 30 % |
| Letter & lexical statistics | Stop words at most T % | 0 % | **25 %** | 10 % |
| Letter & lexical statistics | Average word length at least W letters | 10 % | **50 %** | 45 % |

The largest gaps between the two by-family arms in T1 (numbered list 45 against 5, markdown table 45 against 0) are
mostly formatting near misses by the by-family split: for example, table rows without the outer `|` that the grader
requires.

### Every rule in every template

![Every rule x template, per model](figures/v2_gptoss_heatmap.png)

Each panel is one model; boxed rows are rules that model trained. Reading across:
- **Trained rules are learned unevenly.** Fixed start sentence, given language and opening summary are near ceiling;
  alternating case and Roman numerals stay near 0 even where trained.
- **Base's high cells are the inclusion rules** (conjunctions, transition words, [[NOTE]]). Base passes them largely
  by restating the rule (issue 24). The trained arms rarely restate, which is why they score *lower* than base on
  these rules even where they trained them.
- **T4 (developer message) is the weak column** for the by-family arms across most rules, not just a few.

### By family

![Held-out gain by family](figures/v2_gptoss_families.png)

Gain over base on held-out rules, averaged within each family; families an arm trained have no held-out rules.
- **By-family arms:** Style transfers most, then Statistics, Length and Structure. Word layout gains least.
- **Within-family split:**
  - Style, Bans and Structure transfer most.
  - Inclusion and Language & notation gain little: their held-out operations are "a marker or a word exactly
    twice" and the number notations.
  - Case gains nothing: its held-out operation is the alternating cases, at 0 %.
  - The held-out Length rules (the word caps) are excluded because base already passes them.

### Costs and side effects

![Accuracy, length, restating](figures/v2_gptoss_costs.png)

All three arms lose 6-7 points of answer accuracy, write 33-46 % shorter reasoning, and stop talking about the rule
(62 % → 13 % of traces).

### Rule by rule

| rules held out | clear transfer | little or none |
|---|---|---|
| by the by-family split | sports commentator (70 % in seen templates), pirate speak (43-53 %), series of questions, every sentence ≤ 12 words, average word length, numbered list, one word per line, XML, markdown table (by-family single-template arm 47 %, A 3 %) | meow between words (0 %), 2:1 statements to questions, every sentence ≥ 20 words, adjacent words with different first letters |
| by the within-family split | no commas (67 %), start every sentence with a word (67 %), sports commentator, markdown table, pirate speak, numbered list, no word over 8 letters | alternating letter case and alternating word case (0 %), meow, Roman numerals, numbers in words, end every sentence with a token |

As in v1, line-level structure, style and persona transfer. Rules that need an edit to every word or letter (meow,
alternating case, adjacent letters) do not, whether held out by family (by-family split) or as the sibling of a trained operation (within-family split:
alternating case stays at 0 % although that arm trained uniform case).

### Checks on these numbers

- **Passing held-out traces rarely restate the rule** (mostly 0-15 % of passes).
- **The judged rules look right.** Sampled pirate-speak and commentator passes are in that style throughout. The judge
  leans strict: a fairly piratey trace with markdown steps was failed. If anything, these numbers understate.
- **Shorter reasoning is not driving the headline.** Twelve rules pass mainly in short traces (passing traces under
  half the length of failing ones), because a shorter trace has fewer chances to break a rule. Removing all twelve
  changes the held-out scores by at most 2.5 points: by-family 24.0 → 24.2, by-family single-template 33.5 → 32.7, within-family 28.0 → 26.2.
- **The two by-family arms fit their training data equally** (final training loss 1.21 for both), so the single-template arm's lead is not a
  difference in fit. Part of it is grader strictness: the by-family split's markdown tables often omit the outer `|` and fail.

### What base is doing, and what that means for "transfer"

Base gpt-oss applies most formatting rules to its **final answer, not its reasoning**. Asked for pirate speak, it
reasons in plain English and answers "Arrr, let's hoist the sail o' knowledge!". Asked to reason in Russian or French,
its reasoning stays English and the answer switches language. That is why base scores 0 % on pirate speak, the
commentator and given language, while the arms reach 40-96 %. Part of what training teaches is therefore **where an
instruction applies** (the reasoning rather than the answer), which a held-out rule inherits, rather than how to
perform each new operation. The two are hard to separate with these data.

![Every rule](figures/v2_gptoss_rules.png)


## Issues log

Every problem found while building and checking the v2 split, how it was found, and what was done. "Found by"
names the check that caught it, which shows which checks were worth having.

### Rule choice

| # | issue | found by | fix |
|---|---|---|---|
| 1 | "No parentheses or brackets" is passed by 47 % of base gpt-oss traces. | calibration base-rate scan | replaced by "no colons" (base 3.4 %) |
| 2 | "Exactly five sentences" is short by definition (about 100 words against a 203-word median), so training it teaches shorter reasoning, which leaks into the held-out word caps. | discussion, then the length check | replaced by "every sentence at least 20 words" |
| 3 | "No two adjacent words with the same first letter" and "no word over 8 letters" cannot be produced by an LLM rewrite (0 of 53 and 8 of 53 in a pilot). | pilot build | stay held out in both arms; the within-family split keeps lexical density as its trained statistics operation |

### Compatibility (pairs that cannot share a training example)

| # | issue | found by | fix |
|---|---|---|---|
| 4 | Sentence-based rules cannot be graded inside markup, list numbers ('1.' reads as a sentence end) or table rows. | writing the graders | format conflict added |
| 5 | Re-casing JSON breaks its escapes (`\n` becomes `\N`). | mechanical-edit test | JSON × all caps / alternating cases excluded |
| 6 | A fixed start sentence cannot end with the end-of-sentence token; the end phrase cannot start with "Indeed". | mechanical-edit test | contradictions added |
| 7 | Telegraphic stop-word style and long-word style delete the short conjunctions that the conjunction rule needs. | pilot failures | feasibility conflicts added |
| 8 | Fixed phrases add a sentence; the 2:1 ratio fix inserts short questions, breaking sentence-count and sentence-length rules. | pilot failures | format and feasibility conflicts added |

### Graders

| # | issue | found by | fix |
|---|---|---|---|
| 9 | The opening-summary rule makes language ID say "not English", so every English-list rule failed alongside it. | pilot failures | language check skips the summary sentence |
| 10 | Square brackets, XML tags and "meow" confuse language ID. | pilot failures | stripped before language ID |
| 11 | JSON in a code fence hid the whole trace from the case graders (Redwood masks fenced code). | pilot failures | JSON written without a fence |
| 12 | The alternating-letter grader counted apostrophes as letter positions ("s'agit"). | unit test | counts letters only |
| 13 | The Roman-numeral grader counted the pronoun "I" and words like MIX and DID. | design review | needs 2+ valid numerals of 2+ letters, excluding numeral-like English words |
| 14 | Number rules were drawn for traces with no numbers, which can never pass "at least 3 number words". | pilot failures | number rules only sampled for traces with 3+ numbers; evaluated on numeric questions only |

### Length side effects

| # | issue | found by | fix |
|---|---|---|---|
| 15 | The LLM rewrite pulled every trace towards 150-300 words: short traces inflated about 1.6×, long ones halved. The by-family split's first build was 21 % longer than base, biasing the held-out word caps. | length check | explicit word-count target in the rewrite prompt plus a length gate (0.8× - 10 to 1.3× + 25 words) |
| 16 | "At most 12 words per sentence" was met by cutting content (median trace 84 words). | length check | rewrite splits instead of cuts, plus a word-preserving sentence splitter |
| 17 | Stop-word and long-word rewrites deleted words (traces halved). | length check | rewrite by rephrasing, held to the length gate |
| 18 | "Meow" doubles word count by design; in B it leaked into the held-out "at least 423 words" (27.5 % of training traces against 8.6 % of base; 8.1 % without meow rows). | leakage audit | the within-family split trains line breaking instead of per-word insertion |

### Other leakage

| # | issue | found by | fix |
|---|---|---|---|
| 19 | The LLM rewrite drops colons (it turns "Step 1: ..." lines into prose). 34 % of the within-family split's training traces had no colons against 3.5 % of base, a leak into the within-family split's held-out "no colons". | leakage audit | rewrite told to keep the original punctuation: the leak halved to +13 points but stays over the threshold, spread across many rules. **"No colons" is marked as leaked for the within-family split** and reported separately from the within-family split's clean held-out score. |
| 23 | CoTControl's meow grader exempts gaps at line breaks, so a one-word-per-line trace passed "meow between every two words" with no "meow" at all (7.8 % of the within-family split's training traces once B trained one word per line). At evaluation this would also have credited the wrong behaviour. | leakage audit | grader requires the meow tokens to be present |
| 20 | A word ban in a non-English example would be satisfied by translation. | design review | the keyword is translated into the trace language |

### Prompt text

| # | issue | found by | fix |
|---|---|---|---|
| 21 | the within-family split's first build used the pre-calibration wording ("35 %", "6 letters") while verifying against the calibrated thresholds. | review of the build | prompts re-rendered from the saved arguments |
| 22 | "No first-person words (I, me, ...)" listed English pronouns in non-English examples. | reading training prompts | pronoun list localised |

### Final audit (training sets used for training)

| arm | examples | held-out leaks | length vs base | template leaks |
|---|---:|---|---|---|
| by-family split (A) | 554 (subsampled from 835) | none (largest +3 points) | 1.12× overall | none |
| within-family split (B) | 554 | "no colons" +13 points (marked leaked); all others within +3 | 1.07× overall; 4 rules at 1.16-1.20× | none |
| by-family single-template arm | the by-family split's 554 examples, all in T1 | as A | as A | none |

### Found in the evaluation

| # | issue | found by | handling |
|---|---|---|---|
| 24 | Inclusion rules can be passed by **restating the rule**. Base writes "use each coordinating conjunction: for, and, nor, but, or, yet, so" in its reasoning, which satisfies the grader: base passes conjunctions 95 % when restating against 0 % when not (transition words 94 % against 12 %; [[NOTE]] 94 % against 59 %). The trained arms rarely restate (13 % against 62 %), so they appear to get worse at rules they trained. | reading outputs behind base's 86 % | these rules are already outside the held-out headline (base above 40 %); in-distribution comparisons on them are reported with restating traces separated. A grader that ignores quoted rule text would fix it at the source. |
| 25 | Base applies style and language rules to the final answer rather than the reasoning (pirate speak, other languages). | reading outputs behind base's 0 % | interpretive: see "What base is doing" |
| 26 | Calibration on unconstrained traces does not predict base compliance when the rule is asked. "At most 82 words" was set so 10 % of unconstrained traces pass, but base passes 56 % when asked (≥ 423 words: 60 %). Length transfer therefore cannot be measured on gpt-oss. | base evaluation | rules base passes on 40 % or more are excluded from held-out scores, so no number is inflated; but length transfer is unmeasurable here. Gemma uses the same calibration; calibrating with the rule in the prompt would be the better design for future models. |

### Process

| # | issue | found by | fix |
|---|---|---|---|
| 27 | The queue that was meant to start the Gemma run waited about 3 hours after its downloads finished: its wait condition matched a leftover shell whose command text contained the same words (the self-matching problem in METHODOLOGY #40). | status check | queue stopped and the Gemma stage started directly; wait conditions must match process names anchored to the start, never free text |

### Open

- **Dataset size:** the by-family split kept 835 examples and the within-family split 554; both by-family arms were subsampled to the same 554 (seeded), so data size does
  not confound the by-family against the within-family split.
- **Uneven coverage in the within-family split:** examples per training rule range from 43 (one word per line) and 61 (long sentences) to
  391 (questions). Rules with little training data may show little in-distribution learning.
- **Calibration pool:** thresholds were calibrated on base traces of the training question pool, while evaluation uses
  Redwood's pool. Base pass rates at evaluation may not be exactly 10 %; the base run will show them.
- **Q5 comparison:** Q5 used 5 rules per example and v2 uses 7.
