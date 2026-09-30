# Why did the Redwood run find transfer on gpt-oss-20b when ours did not?

*Source: the LessWrong shortform by abhayesian (comment `cryGg9ShEqhKFdyD7`) and the released code at
github.com/redwoodresearch/chippy-final-codebases, folder `cot-controllability-steering-vectors`, read in full for
the instruction suite, data build, training and evaluation. The work was done by an automated research scaffold at
Redwood Research; the authors describe its rigour as "at or slightly below a typical MATS project". Their numbers
below come from the released `figure_data/ft_deliverable_cdel_vs_ctrldel.json`. Ours come from `GPTOSS_FINDINGS.md`.*

## What they actually found

Their headline is a LoRA fine-tune on gpt-oss-20b that raises held-out CoT-control compliance from 1.6 % to 13.9 %
(uplift +12.3 pp, 95 % CI +10.4 to +14.2), and a single steering vector that reproduces it. Per held-out
instruction, on 100 held-out tasks each, strict "effective control" (compliant, not meta, genuine, not truncated,
not degenerate):

| held-out instruction | relation to the training set | base | fine-tune | matched control |
|---|---|---:|---:|---:|
| bullet ("every line starts with '- '") | new category (formatting) | 0 % | **52 %** | 0 % |
| terse_25w ("at most 25 words") | same category as trained brief_50w and length_30_60w | 14 % | **61 %** | 1 % |
| numbered list | new category (formatting) | 0 % | 9 % | 0 % |
| no_word_so | same category as trained no_the / no_commas | 0 % | 3 % | 2 % |
| initial_caps, include_exactly_twice, section_headers, xml_steps, child_explanation | mixed | 0 % | 0 % | 0 % |

So their result is also narrow: two instructions carry almost all of it, one of them is a tighter version of a
trained length rule, and five of nine held-out instructions do not move. Their README says so ("carried by ~2–3
instructions; 5 of the 9 held-out instructions stay flat"). The genuinely cross-category transfer is bullets, 0 →
52 %, plus numbered lists at 9 %.

That makes it the same shape as our Qwen3-8B result: one novel whole-trace format moves strongly (their bullets,
our JSON on Qwen3-8B), a near-twin moves (their terse ↔ brief, our end-of-sentence ↔ trained end-of-sentence), and
everything else stays at zero. The real question is why gpt-oss produced a bullet-type transfer for them and
nothing comparable for us.

## Setups side by side

| | Redwood | ours |
|---|---|---|
| trained instructions | **12, spread over 5 categories**: casing (all caps, all lowercase), suppression (no commas, no "the"), inclusion (use "therefore", include [[NOTE]], start with a fixed sentence), length (≤ 50 words, 30–60 words), style (questions, second person, Spanish) | 6: language, word budget, capital, end phrase, no comma, end-of-sentence word |
| constraints per example | **one** | 1, 3 or 5 (arms S1, T3, Q5) |
| training size | up to 55 examples per source × 6 sources × 12 instructions (about 4,000 at most, after gating) | about 915 per arm |
| task pool | GSM8K, MATH, MMLU-Pro, OpenBookQA, ARC, ReasonIF; source traces capped at 600 words | ReasonIF-style pool, 937 questions, no length cap on sources |
| editing | programmatic, or Claude Opus for style/Spanish/questions; every target gated by Opus judges for compliance, genuineness, **no meta-discussion**, faithfulness to the source reasoning, concluding the gold answer, round-trip parse | programmatic, or gpt-4.1-mini for translation, condensation and end-of-sentence; gated by the rule grader only |
| answer target | the **gold** answer in a stable format (letter, or `\boxed{}`) | the model's own stage-1 answer (untagged) |
| prompt wording | every instruction, trained and held out, uses the same frame: "Formatting requirement for your reasoning: … your chain of thought (your step-by-step reasoning) …", placed in the user message | ReasonIF "rules" template for training; the CoTControl "Requirement … do not mention" template and our own IFBench wording for the transfer tests |
| LoRA | rank 32 on **MLP / MoE experts + attention + unembedding**, bf16 model (Tinker) | rank 32 on attention q/k/v/o only, 4-bit base (Unsloth) |
| optimisation | lr 2e-4, **3 epochs**, batch 128, linear warm-up and decay | lr 1e-4, 1 epoch, batch 4 |
| context cap | 2,048 tokens | 4,096 |
| decoding in eval | **greedy (temperature 0)**, medium effort | temperature 1, top_p 1, medium effort |
| metric | "effective control": compliant *and* not meta *and* genuine *and* not truncated or degenerate; casing checked with LaTeX and code masked | binary compliance and continuous score; meta not excluded; no LaTeX masking on gpt-oss |
| control arm | the same prompts with the unedited, non-complying trace | the same traces under a plain prompt without any rule |
| held-out set | 9 instructions, 4 of them a whole category (formatting) never trained | 10 CoTControl modes and 30 IFBench-derived rules |

## What most plausibly explains the difference, in order

**1. Instruction diversity, not constraints per example.** They train twelve different instructions across five
categories, one per example; we train six rules, stacked. The categories they train (casing, suppression,
inclusion, length, style including a language switch and a question form) cover much more of what "a rule about
my reasoning" can look like. Our results already pointed this way: on Qwen3-8B, T3 with twelve distinct
combinations beat Q5 with two, and on gpt-oss our Q5 was no better than T3 anywhere except five-rule prompts.
Their design suggests that the variety of rule types, not the number of rules stacked in one example, is what
builds a transferable "follow the reasoning-format instruction" behaviour.

**2. The same prompt frame for training and held-out rules.** Every one of their instructions, trained or held
out, is introduced by the same sentence and names the target the same way ("your chain of thought (your
step-by-step reasoning)"). Their mechanism analysis shows the fine-tune works by making late attention heads read
the instruction and land on the format specifier (bullet specifier attention 2.3 → 6.5). A consistent frame makes
that routing easy to reuse for a new specifier. Our CoTControl test changed the frame entirely, and our never-seen
rules used short "When reasoning, …" sentences. Their code comments call the explicit "your reasoning" wording
"essential" because of a channel-routing finding: without it gpt-oss applies formatting instructions to the final
answer.

**3. The transferring format is one the base model already produces, but in the answer.** Their README notes that
base gpt-oss "readily reformats its final answer" while almost never formatting its reasoning. Bullets are gpt-oss's
native answer style. What the fine-tune teaches is to apply the requested format to the analysis channel; bullets
move because the model already knows how to write them. This is exactly our Qwen3-8B JSON finding (base wrote JSON
in its answer 37 of 40 times, fine-tuning moved it into the reasoning). Our never-seen and CoTControl sets for
gpt-oss contained no format that gpt-oss natively uses in answers: no bullets, no numbered lists, no headers. The
nearest we had were newline_words and line_indent, which are not formats any model writes naturally.

**4. A much larger update.** Their adapter covers the MoE experts, attention and the unembedding, trained for three
epochs at twice our learning rate on up to four times our data. Ours covers attention only, one epoch. Their
steering-vector result (one 2,880-number vector at layer 10 matches the fine-tune) says the *capacity* needed is
tiny, so the adapter's size is not the bottleneck; but the number and diversity of gradient signals it sees is.
Their mechanism is attention-based, which our attention-only adapter could in principle learn; the difference is
more likely the data and epochs than the target modules.

**5. Cleaner training targets.** Their targets pass an Opus judge for "no meta-discussion" and for faithfulness to
the original reasoning, and they end on the gold answer. Our targets passed only the rule grader. On gpt-oss we
found that base restates the rule in two thirds of its traces; any narration left in training targets teaches the
model to talk about the rule rather than silently apply it. Their base meta rates on held-out prompts are 43–94 %,
and fine-tuning drops them to 0 %: the fine-tune learned to stop narrating, which is part of what "effective
control" rewards.

**6. Greedy decoding and a strict-but-fair metric.** Temperature 0 removes sampling slips, which matter under
all-or-nothing formats; LaTeX masking removes an impossible requirement from the casing checks. Both raise
measured compliance for every arm, so they help the absolute numbers more than the uplift.

**7. Short tasks.** Source traces are capped at 600 words and the held-out tasks are weighted toward short
sources (ARC, GSM8K, OpenBookQA). Every-line formats are much easier to hold for 150 words than for 1,500. Our
trace-length finding on Qwen3-8B (essentially no binary passes above 2,000–4,000 tokens) applies here.

## What does not explain it

- **Model.** Same gpt-oss-20b, same medium reasoning effort, both served in MXFP4 for evaluation.
- **Base floor.** Both bases are near zero on the held-out rules (theirs 1.6 %, ours 1.5 % on CoTControl).
- **Multi-constraint training.** They did not use it. Their result argues that it is not needed for transfer and
  that single-instruction training on a diverse instruction set is at least as good.

## What it means for our experiments

1. **Our gpt-oss null is not strong evidence against transfer.** Our test sets did not include the kind of format
   that transfers (a native answer format relocated to the reasoning), and our training set had low instruction
   diversity. The two runs are consistent with one account: fine-tuning teaches "apply the prompt's formatting
   instruction to the reasoning channel", and it shows up on formats the model already writes elsewhere.
2. **Cheapest direct test (no training, about an hour of GPU).** Evaluate our existing gpt-oss checkpoints (base,
   R, S1, T3, Q5) on their nine held-out instructions with their exact wording and greedy decoding. If bullets
   move for our arms too, the difference is in the test set; if they do not, it is in the training recipe.
3. **Recipe test.** Train one arm on their instruction diversity (twelve single-rule instructions, their frame)
   with our pipeline and attention-only adapter, and compare against our Q5. That separates diversity from LoRA
   scope and epochs.
4. **Borrow three things regardless.** A consistent "your reasoning" frame across train and test; a no-meta gate
   on training targets; and an effective-control metric that excludes narrated, truncated and degenerate traces.


## Update: our checkpoints on their nine held-out instructions (2026-09-30)

We ran our gpt-oss checkpoints on Redwood's nine held-out instructions with their exact prompt assembly, their
100 held-out tasks per instruction, their scorers, greedy decoding and medium effort (`scripts/run_redwood_eval.py`,
results in `results/redwood_eval/`). Metric: raw compliance, which is their `raw_compliance`; their
`effective_control` also needs Opus meta and genuineness judges, not run here. child_explanation judged by
gpt-4.1-mini with their criterion.

| held-out instruction | base | R (control) | S1 | T3-60 | T3-final | Q5 | Redwood base → FT |
|---|---:|---:|---:|---:|---:|---:|---:|
| bullet | 0 | 0 | **68** | **79** | **79** | **77** | 0 → 57 |
| terse_25w | 13 | 25 | **89** | **88** | **81** | **91** | 16 → 61 |
| numbered | 0 | 0 | 0 | **17** | 0 | 0 | 0 → 9 |
| section_headers | 1 | 1 | 0 | **23** | 0 | 0 | 1 → 0 |
| no_word_so | 0 | 0 | **15** | **25** | 6 | **14** | 0 → 3 |
| include_exactly_twice | 2 | 2 | **14** | 8 | 3 | 4 | 2 → 0 |
| xml_steps | 0 | 0 | 0 | 6 | 0 | **10** | 0 → 0 |
| child_explanation | 0 | 0 | 2 | 8 | 0 | 5 | 0 → 0 |
| initial_caps | 0 | 0 | 0 | 1 | 0 | 0 | 0 → 0 |
| **macro over nine** | **1.8** | **3.1** | **20.9** | **28.3** | **18.8** | **22.3** | 1.8 → 14.4 |

Bold = significantly above the control arm R (Fisher, one-sided, p < 0.05, n = 100 each).

**The difference was the test set, not the training recipe.** On their instructions our checkpoints transfer as
much as or more than their fine-tune: bullets 68–79 % against their 57 %, terse 81–91 % against 61 %, macro
19–28 % against 14 %. The control arm R stays at base (bullets 0 %), so the gain comes from the constraint training.
The bullet passes are genuine: 79 of 79 inspected T3-60 passes are bulleted reasoning about the question, none
mention the format, and the answers stay correct. Accuracy is unchanged (79–82 % against base 82 %).

Three details:

- **terse_25w is not a clean transfer for us.** Our trained number_words rule is a word budget, so the 25-word rule
  restates a trained constraint, as it does in Redwood's run (brief_50w).
- **T3-60 transfers most broadly** (numbered 17 %, section headers 23 %, XML 6 %), as the early-checkpoint peak on
  Qwen3-8B predicted; by step-final those three return to zero while bullets stay at 79 %.
- **Truncation rises for the trained arms** (base 23, T3-final 99 of 900), concentrated on numbered, initial_caps,
  section_headers and XML; truncated rollouts count as non-compliant, so these rates are, if anything, low.

**What this changes.** Our own never-seen and CoTControl suites contained no native answer format, so they showed
almost nothing. Redwood's suite contains bullets and lists, gpt-oss's natural answer register, and there the same
checkpoints transfer strongly. Across all three models the rule holds: multi-constraint (or diverse-constraint)
SFT teaches "apply the prompt's formatting instruction to the reasoning", and it reaches formats the model already
produces elsewhere (JSON on Qwen3-8B, bullets on gpt-oss), not formats it never produces.

## Caveats about their result

- One model, one seed, and a single Claude Opus judge for the style and meta labels.
- The work was produced by an automated agent; the authors did not do a detailed code review.
- Their fine-tune evaluation was generated with the model merged to bf16 on an H100, ours with an adapter on the
  MXFP4 base; small numerical differences are possible.
- Their control arm (same prompts, non-complying traces) is the analogue of our unlearning arm, and it lowers
  compliance below base on several instructions (terse 14 → 1 %, brief 45 → 7 %), consistent with our unlearning
  finding that instruction-ignoring examples remove control broadly.
