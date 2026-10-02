# Many-rule SFT: findings (Qwen3.8-27B, gpt-oss-20b, R1-Distill-Llama-8B)

*2026-10-01. Plan and design: `MANY_RULES_PLAN.md`. Base Qwen3.8-27B, Q5 (6 rules, 5 per example), and two new arms
trained on about 32 rules with 7 per example:*
- *A: whole families held out;*
- *B: every splittable family on both sides, split by operation.*

*Setup: QLoRA, one epoch on about 440 examples, Red Hat's INT4 weights for evaluation, single-rule prompts identical
across the four models. 20 prompts per condition (29 for Redwood's). Figures come from `scripts/report_many_rules.py`.*

## Headline

![Held-out conditions only](figures/many_headline.png)

Training on many more rules roughly triples transfer to rules the model never saw.

- **Shared core** (six conditions held out by both arms and by Q5): macro 1 % for base, 11 % for Q5, 29 % for A and
  31 % for B.
- **Each arm's own held-out set:** A reaches 25 % against Q5's 12 %, and B reaches 19 % against Q5's 10 %.
- The micro numbers tell the same story.

Each bar counts only conditions that the model shown never trained on, and that Q5 never trained on either. The
conditions base already passes (section headers, stop words, conjunctions) are left out.

**The within-family split (B) does not transfer more than the family split (A).** The two are level on the shared
core. B's own held-out set scores lower. That set consists of the near siblings of B's trained rules: alternating
case, word bans and the per-sentence rules.

## What transfers and what does not

![Every condition](figures/many_per_condition.png)

1. **Structure and style transfer strongly**, with none of these rules trained by A:

   | condition | Q5 | A |
   |---|---:|---:|
   | bullets | 28 % | 76 % |
   | numbered | 31 % | 69 % |
   | XML steps | 10 % | 38 % |
   | questions | 10 % | 41 % |
   | child explanation | 7 % | 24 % |
   | second person | 3 % | 17 % |

2. **Word-level layout and letter-level rules do not transfer.** Meow between words, one word per line, square
   brackets and no-consecutive-initials stay at 0–10 % for every model.
3. **Within-family siblings transfer weakly.** Holding out word bans in B leaves them at 0–31 %, at or below Q5. B
   trained the specific-word inclusions, but that did not carry over to the bans. Alternating case stays at 5 %, even
   though B trained uniform case.

## Does training on a rule matter?

![A against B](figures/many_a_vs_b.png)

Each point is one condition, A's score against B's. Off the diagonal, the arm that trained the rule usually does
better, but the gap is often small:

| condition | A | B | who trained it |
|---|---:|---:|---|
| no "so" | 55 % | 14 % | A |
| no "the" | 52 % | 31 % | A |
| word suppression | 20 % | 0 % | A |
| JSON | 0 % | 20 % | B |
| questions | 41 % | 38 % | B |
| XML steps | 38 % | 34 % | B |

For questions and XML steps, A matches B without having trained the rule. Most of the gain is a general skill,
following a format instruction in the reasoning, rather than the specific rule.

**Some trained rules are not learned at all:**
- the end-of-sentence word, repeat-sentence and start = end word stay at 0 % in both arms;
- the end phrase falls from 65 % (Q5) to 10 %;
- all capitals falls from 65 % to 40–55 %.

Each rule now appears in about 60–150 examples, against about 380 per rule in Q5, so per-rule learning is shallower.

## Cost

![Accuracy and length](figures/many_accuracy_length.png)

**Accuracy on Redwood's tasks** is 86 % for base, 89 % for Q5, 84 % for A and **74 % for B**, so B loses 12 points.
Reasoning is shorter for every fine-tuned model: a median of 86–110 words, against 271 for base. B's training mix
leans on terse, telegraphic and question-style rewrites. That probably explains why its reasoning is shortest and its
accuracy lowest, but I have not tested that.

## Summary

- More rules widen transfer: three times Q5 on the shared core, with A at no meaningful accuracy cost.
- Splitting within families (B) does not strengthen transfer, and it costs accuracy.
- Transfer goes to line-level structure and style (lists, XML, questions, register), not to word-level or letter-level
  operations, and only weakly to siblings of the trained rules.
- Many specific trained rules stay unlearned. The broader training seems to teach "obey a formatting instruction in
  the reasoning" more than any single rule.

## Replication on gpt-oss-20b

![gpt-oss held-out conditions](figures/many_gptoss_headline.png)

*Same registry, splits and 7 conditions per example. The setup otherwise follows the earlier gpt-oss runs:*
- *about 900 examples per arm (A 919, B 878), the same size as gpt-oss's own Q5 (906);*
- *attention-only LoRA, one epoch;*
- *medium reasoning effort, no answer-tag line;*
- *40 prompts per CoTControl mode and per IFBench rule, 20 per ReasonIF rule;*
- *Redwood: 100 tasks per instruction with greedy decoding, as in the earlier gpt-oss Redwood runs.*

The result holds on a second model family.

- **Shared core:** base 0 %, Q5 15 %, A 33 %, B 30 % (macro). That is about twice Q5, where Qwen showed about three
  times.
- **Each arm's own held-out set:** A reaches 38 % against Q5's 12 %, and B reaches 36 % against Q5's 19 %.
- **Accuracy on Redwood's tasks:** 84 % for base and 80 % for all three fine-tuned models. B does not lose more than
  the others here, unlike on Qwen.

**Where gpt-oss differs from Qwen.** The within-family split transfers well on gpt-oss. B never trained a word ban,
yet it reaches 66–93 % on no "so", no "the" and no "answer", close to A, which trained them. On Qwen, B stayed at
0–31 % on the same bans. Part of this was already present: gpt-oss's Q5 reaches 54–74 % on two of the bans.

**Held-out transfer that is new on gpt-oss** (each condition held out by the arm named):

| condition | base | Q5 | arm | score |
|---|---:|---:|---|---:|
| numbered | 0 % | 0 % | A | 74 % |
| section headers | 1 % | 0 % | A | 81 % |
| XML steps | 0 % | 10 % | A | 27 % |
| questions | 5 % | 6 % | A | 82 % |
| "Indeed" as first word of each sentence | 0 % | 0 % | B | 18 % |

**The same failures as on Qwen.** The same word-level and letter-level rules stay at 0–10 % for every arm: meow,
one word per line, no consecutive initials, alternating case and emoji at the end of each sentence.

Per-condition figures: `figures/many_gptoss_per_condition.png` and `figures/many_gptoss_a_vs_b.png`.

## Replication on DeepSeek-R1-Distill-Llama-8B

![R1-Distill-Llama held-out conditions](figures/many_r1_headline.png)

*A third model family (Llama base). The whole chain was run fresh: base, Q5, A and B.*
- *Training: QLoRA on a 4-bit base, all linear layers, one epoch, about 900 examples per arm (Q5 916, A 920,
  B 872).*
- *Evaluation: served in bf16, with DeepSeek's sampling (T 0.6, top-p 0.95).*
- *Prompts: 20 per condition; Redwood 50 tasks per instruction.*

The pattern holds, and the gap is larger than on the other two models, because Q5 barely transfers on this model.

- **Shared core:** base 0 %, Q5 3 %, A 30 %, B 27 % (macro).
- **Each arm's own held-out set:** A reaches 23 % against Q5's 5 %, and B reaches 16 % against Q5's 3 %.
- **Accuracy on Redwood's tasks:** 67 % for base and Q5, 64 % for A, 62 % for B.
- **Reasoning length:** shorter after many-rule training, a median of 134–146 words against 399 for base.

**Held-out structure transfer,** for rules A never trained:

| condition | base | Q5 | A |
|---|---:|---:|---:|
| bullets | 0 % | 14 % | 86 % |
| numbered | 0 % | 0 % | 80 % |
| section headers | 2 % | 0 % | 60 % |
| XML steps | 0 % | 0 % | 32 % |

**Like Qwen, unlike gpt-oss,** style rules transfer weakly: questions reach 4 % and second person 4 % in A, against
48 % and 24 % in B, which trained them. Word bans held out in B reach 52–62 % on no "so" and no "answer", but stay
near 0 % on the CoTControl word-suppression modes and on no "the". The same word-level and letter-level rules stay
at 0–5 % on all three models.

## Across the three models

| macro, held-out | Qwen3.8-27B | gpt-oss-20b | R1-Distill-Llama-8B |
|---|---:|---:|---:|
| shared core: base / Q5 / A / B | 1 / 11 / 29 / 31 | 0 / 15 / 33 / 30 | 0 / 3 / 30 / 27 |
| A's held-out: Q5 → A | 12 → 25 | 12 → 38 | 5 → 23 |
| B's held-out: Q5 → B | 10 → 19 | 19 → 36 | 3 → 16 |
| accuracy: base / A / B | 86 / 84 / 74 | 84 / 80 / 80 | 67 / 64 / 62 |

On all three models, many-rule training lands at about 30 % on the shared core, whatever Q5 managed. In every case
the gain comes from line-level structure: bullets, numbered steps, section headers, XML. Splitting within families
(B) never beats splitting by family (A) on the shared core.

## Caveats

- **Noise.** One seed and 20–29 prompts per condition, so single-condition differences under about 25 points are
  noise. The pooled numbers cover 6–14 conditions.
- **gpt-oss restates the rule.** It often repeats the instruction in its reasoning. That cannot help it pass a ban, but
  it can inflate inclusion rules.
- **Judge.** Second person and questions are judged by gpt-4.1, the same judge that verified the training data. B
  trained against that judge, so B's numbers on those two could partly reflect fitting the judge. A never saw those
  rules.
- **Short reasoning helps some rules.** It satisfies terse, "no word more than 10 times" and the word bans more
  easily. Every fine-tuned model writes shorter reasoning than base.
- **A and B differ in more than the split.** Their mixes differ in size (456 against 427 examples) and in coverage per
  rule, as well as in which rules they train.
- **Redwood macro.** Several Redwood instructions are now trained, so no Redwood macro over all nine instructions is
  quoted.
