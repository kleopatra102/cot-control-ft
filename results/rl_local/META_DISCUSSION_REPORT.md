# Talk about the rules in controllability training: what we do and why

25 November 2026. This report explains the "remark step" of the programmatic controllability recipe from the
beginning, for a reader who was in neither working session. The record of each decision, in order, is in
META_DISCUSSION_REMARKS_DECISIONS.md. The rules themselves are described in PROGRAMMATIC_RULES.md.

## Summary

- When a reasoning model is given rules about how to write its reasoning, it often talks about those rules in the
  reasoning ("I need to use 'hence' twice"). We call such a sentence a remark.
- Earlier training recipes removed remarks from the training targets. Models trained that way mentioned their rules
  far less than the base model. That is a confound: a later finding that "the reasoning reveals less" could come from
  the recipe and not from controllability.
- The recipe now gives each training target the remarks the base model itself makes on that exact prompt. The base
  model is sampled once per training row, a judge finds its remark sentences, and the ones that qualify are copied,
  word for word, into the target.
- Result for R1-Distill-Qwen-7B: 43.9 percent of English training rows have a remark, against 46.3 percent of the
  base model's traces on the same prompts. For R1-Distill-Llama-8B: 41.4 against 42.7 percent.
- The match is looser in two respects. Targets have fewer remarks per row than base (about 80 percent of base in
  English rows), because remarks that are wrong, vague or broken are left out. Rows written in another language have
  fewer still (about 56 percent of base), because translation damages some remarks and those are left out too.
- Nothing has been trained with this recipe yet. Whether a trained model keeps the base rate of remarks is the test
  this step exists for, and it has not been run.

## 1. What a remark is

A training prompt contains a question and six or seven rules about the form of the reasoning, for example "End every
non-empty line with its number", "Use the word 'hence' at least twice", "Write the reasoning in French". The model
is trained to follow them.

A remark is a sentence in the reasoning that talks about those rules: it restates one, plans around it, or notes
that it is following it. Three real examples from the base R1-Distill-Qwen-7B on training prompts:

- "I need to make sure the sentence 'The plan is on track.' appears twice."
- "Oh, and every third word needs to be in capital letters."
- "Each line must be exactly five words, with words in double angular brackets."

A sentence that merely follows a rule is not a remark. "I'll tally the results in a ledger" uses two required words
but says nothing about the rule that requires them.

The literature calls this meta-discussion. We use "remark" for one sentence and "rule talk" for the behaviour.

## 2. Why it matters, and what earlier recipes did

The project asks whether controllability training makes a model's reasoning less useful to a monitor. One thing a
monitor can use is the model saying what it was told to do. If training removes that as a side effect of how the
data was made, we would measure the side effect.

What happened before:

| Recipe | How remarks were treated | What trained models did |
|---|---|---|
| First recipes (several model families) | The rewriting model removed talk about the rules from every target | Restated their rules in about 10 percent of traces, down from 72 to 93 percent for base |
| Previous recipe ("Bnc") | An opening remark written by GPT-4.1 was added to a share of targets equal to the base model's rate with one rule in the prompt | Trained R1-Llama remarked in 2 of 100 traces on training-style prompts; base did in 14 of 100 |

So removing remarks removed rule talk, and adding one synthetic opening remark at the right overall rate did not
bring it back. Two things were wrong with the synthetic remark: it was not the model's own wording, and it sat at
the opening, whereas base models put most remarks late in the trace (section 6).

The programmatic recipe makes this worse by default. Its targets are the base model's own unconstrained reasoning
with the rules applied by code. Code adds no remarks, so without this step the rate in the targets would be zero.

## 3. The method

For each model, and for each of its 900 training rows:

1. **Sample the base model once on the row's exact training prompt** (question plus its six or seven rules), with
   the model's usual sampling settings. If the reasoning does not close or is empty, sample again, up to three times.
2. **Find the remarks.** The reasoning is cut into sentences by code. A judge (GPT-4.1) reads the rules, the question
   and the numbered sentences, and labels every sentence that talks about the rules (section 4). A second pass shows
   the judge only the unlabelled sentences that contain a rule's own string or a rule-related word, to catch misses.
3. **Decide which remarks are copied.** A remark is copied as the base model wrote it unless one of the filters in
   the table below removes it. Nothing is rewritten and nothing is generated.
4. **Insert.** The row's source text is the base model's reasoning on the same question without any rules. Each copied
   remark is appended to the end of the paragraph nearest to its relative position in the base trace (a remark 80
   percent of the way through goes to the paragraph ending nearest 80 percent). Paragraph ends are used so that no
   sentence or list is ever split. Remarks that land in the same paragraph stay together in their original order.
5. **Translate, for a row with a language rule.** The source text and each remark are translated separately by a
   local translation model. Before translation, any rule string a remark mentions is put in double quotation marks,
   which the translator leaves untouched, so the remark still names the right word. A third model call (GPT-4.1)
   compares each translated remark with its English original; if the meaning, the speaker or the tense changed, or it
   became a command to a reader, the remark is left out.
6. **Apply the code rules and grade.** The rules are applied to the whole text, remarks included, so a remark comes
   out in capitals, with separators, with line numbers, like everything else. The rules' own insertions (required
   words, markers, sentences) are placed outside remark sentences and counted outside them. Every rule is then
   graded by code; a row is kept only if all pass.
   A further code check fails any row in which a required word, sentence or marker is present only inside a remark.

If graders fail with the remarks in, the build tries again leaving out the remarks that name a string of the failing
rule, then all remarks that name a rule string, then all remarks. In the final builds this was needed for one row.

### What is left out, and why

| Filter | Reason | Decided by |
|---|---|---|
| Kind is "struggle", "refuse" or "other" | Targets should show plans and acknowledgements, not complaints or refusals | Judge label |
| Describes the rule wrongly | Do not train misstatements of the rules | Judge label |
| Does not stand alone ("that last line should have been capitals") | It refers to text that is not in the target | Judge label |
| Written in the special form a rule asks for, or contains a marker not in the rules | It is a half-formatted line, not a sentence about the rules | Judge label and code |
| Says the rule is already satisfied ("I've used it twice now"), including past-tense statements of having done it | Training such claims teaches the model to assert compliance, which is close to text aimed at a monitor | Judge label and code |
| States a number differently from the rule ("at least once" for "at least twice") | The judge's accuracy label missed these | Separate judge question |
| General sentence with no reference to the rules ("Let me think step by step") | Not a remark | Code |
| Points back at a remark that was left out ("I need to include that somewhere") | Its antecedent is gone | Code |
| Longer than 60 words, or repeats a remark already used in the row | A run of text without sentence breaks was taken for one sentence | Code |
| Fewer than four words | A fragment | Code |
| Translation changed it | See step 5 | Separate judge question |
| Written by the model in the row's language but containing other languages | Would break the language rule inside a sentence | Separate judge question |

Statements of following in the present tense ("I am writing this in capitals as asked") are kept.

### A worked example

Row 426 of Qwen-7B's draw. The question is "Can you please help me follow the account @AI_TechNews on Twitter?" and
the prompt carries six rules: end every non-empty line with its number in the form (L1), (L2); write the reasoning in
English; use the word "therefore" at least once; capitalise the first letter of every word; include the exact
marker ">>>" somewhere; begin every non-empty line with a bar and a space.

**What the base model did on this prompt.** Its reasoning had 28 sentences. The judge labelled 1 of them as a remark; this one, 75 percent of the way through, was copied:

> Also, I need to end each non-empty line with its number in the form (L1), (L2), etc., and include the exact marker >>> somewhere.

**The source text** is the same model's reasoning on the same question with no rules, three paragraphs. Its second
paragraph is:

> I should explain that I can't follow the account for them, but offer alternative help. Maybe suggest ways they can do it themselves, like going to Twitter, searching for the account, and clicking the follow button. Alternatively, I could provide information about the account, but following is a direct action that I can't perform.

**After insertion** the remark is appended to that paragraph, whose end is the nearest paragraph end to the remark's
position.

**After the code rules**, the same paragraph in the training target reads:

> | >>> I Should Explain That I Can't Follow The Account For Them, But Offer Alternative Help. Maybe Suggest Ways They Can Do It Themselves, Like Going To Twitter, Searching For The Account, And Clicking The Follow Button. Therefore. Alternatively, I Could Provide Information About The Account, But Following Is A Direct Action That I Can't Perform. Also, I Need To End Each Non-empty Line With Its Number In The Form (L1), (L2), Etc., And Include The Exact Marker >>> Somewhere. (L2)

Every word is capitalised, the line starts with the bar and ends with its number, and the remark has been
transformed like the rest. The rule code added "Therefore." as a one-word sentence and put the marker >>> at the
start of the line: both are outside the remark, although the remark itself names the marker. A code check confirms
for every built row that what a rule requires is present outside the remarks, so naming a word or marker in a remark
never counts as using it. The other two paragraphs are the source paragraphs with the same formatting and no other
change.

## 4. The judge

The judge is GPT-4.1 at temperature 0. In plain words its instructions are:

- You see the rules, the question, and the reasoning as numbered sentences.
- List every sentence that talks about the rules. A sentence that only follows a rule, or simply uses a required
  word, is not one. General planning that does not refer to the rules is not one.
- For each, say which rules it is about; its kind (restates, plans, says it is following, struggles, refuses,
  other); whether it describes the rule accurately; whether it stands alone; whether it is plain English prose;
  whether it says the rule is already satisfied; and which rule strings it quotes.

Code, not the judge, turns those labels into "copy" or "leave out".

**How it was checked.** I read 50 judged base traces of Qwen-7B (1,765 sentences, 179 labelled as remarks):

- Of the labelled sentences, almost all were rule talk. About 11 (6 percent) had a wrong detail: a half-formatted
  line marked as plain prose, a wrong count marked accurate, a completion claim not flagged.
- At least 13 clear remarks were not labelled, so the first pass finds at most about 93 percent. Two of the 20
  traces marked as having no remark had one.

Those findings led to the second pass, the separate number check and the code filters above. The hand check was
not repeated after those additions, and it was not done for R1-Llama.

The separate number check is itself imperfect: of 12 remarks it rejected that I read, about 9 were real mismatches
and about 3 were acceptable wording.

## 5. Results

Both models were measured on their own final draw of 900 rows (half with six rules, half with seven; 684 rows in
English, 216 with a rule requiring Spanish, French, Russian or Polish).

### Base model against built targets

| | Qwen-7B base | Qwen-7B targets | R1-Llama base | R1-Llama targets |
|---|---|---|---|---|
| Rows | 899 usable of 900 | 898 built | 900 usable of 900 | 899 built |
| English rows with a remark | 46.3% (316 of 683) | 43.9% (300 of 683) | 42.7% (292 of 684) | 41.4% (283 of 684) |
| English remarks per row | 2.93 | 2.32 | 2.59 | 2.12 |
| Language rows with a remark | 40.3% (87 of 216) | 34.0% (73 of 215) | 32.4% (70 of 216) | 29.8% (64 of 215) |
| Language remarks per row | 2.31 | 1.30 | 2.05 | 1.14 |
| Remark sentences in all | 2,502 | 1,866 | 2,215 | 1,695 |

All figures in this table are measured. The base figures depend on one sample per row and on the judge.

### Where the left-out remarks went

| Reason | Qwen-7B | R1-Llama |
|---|---|---|
| Judge label: kind, accuracy, not standalone, not plain | 200 | 166 |
| States a number differently from the rule | 138 | 89 |
| Translation changed the remark | 89 | 102 |
| Points back at a remark that was left out | 59 | 66 |
| General sentence with no reference to the rules | 53 | 67 |
| Longer than 60 words | 24 | 0 |
| Repeats a remark already used in the row | 24 | 6 |
| Formatted text or a marker not in the rules | 15 | 15 |
| Written in the row's language, not cleared | 14 | 0 |
| Other (fragment, not in English, completion claims, count rule) | 15 | 9 |
| Total left out | 631 of 2,502 | 520 of 2,215 |

Five further remark sentences of Qwen-7B belong to the two rows that could not be built.

### What base models' remarks look like

| | Qwen-7B | R1-Llama |
|---|---|---|
| Traces with at least one remark | 403 of 899 (44.8%) | 362 of 900 (40.2%) |
| With six rules in the prompt | 44.1% | 38.2% |
| With seven rules in the prompt | 45.6% | 42.2% |
| Remarks per trace that has any | 6.2 | 6.1 |
| Traces with 10 or more remarks | 75 | 62 |
| Kind: plan | 2,021 (81%) | 1,747 (79%) |
| Kind: restates the rule | 281 (11%) | 245 (11%) |
| Kind: says it is following | 126 (5%) | 169 (8%) |
| Kind: struggles, refuses or other | 74 (3%) | 54 (2%) |
| In the first third of the trace | 250 (10%) | 281 (13%) |
| In the middle third | 576 (23%) | 511 (23%) |
| In the last third | 1,676 (67%) | 1,423 (64%) |
| About the rules in general, not one rule | 627 (25%) | 449 (20%) |

Two things stand out. Remarks are frequent: with six or seven rules, four traces in ten have some, and those that
do have about six. And two thirds sit in the last third of the trace: these models tend to work on the question
first and turn to the form afterwards. The earlier recipe's single opening remark matched neither.

Which rules attract remarks, counted as remark sentences per 100 prompts containing the rule:

| Rule | Qwen-7B | R1-Llama |
|---|---|---|
| Three required words with counts ("tally", "ledger", "onward") | 155 | 150 |
| Every third word in capitals | 130 | 101 |
| First word of each line in capitals | 63 | 64 |
| Last word of each line in capitals | 48 | 63 |
| Five words per line | 52 | 48 |
| Copy the question at the start | 4 | 2 |
| Language rule set to English | 2 | 2 |

Rules that need counting or careful placement draw the most talk; rules that are done once draw almost none.

### Length

| Median per row | Qwen-7B control | Qwen-7B treated | R1-Llama control | R1-Llama treated |
|---|---|---|---|---|
| Words | 534 | 586 | 460 | 509 |
| Model tokens | 670 | 985 | 577 | 898 |

Control is the same question with the model's unedited reasoning and no rules. In rows that have remarks, the
remarks add a median of 66 words for Qwen-7B and 57 for R1-Llama. The larger part of the token difference comes
from the rules (capitals, separators, translation), not from remarks. Translated rows are about 2.3 times their
control in tokens.

## 6. What readers found on built rows

Built rows were read in several rounds as the method changed. Reader agents were given one row each, since larger
batches were stopped by a safety filter.

Final round, on the builds the training files come from: 16 rows by reader agents (8 per model, half English, half
other languages), all reported, and 45 rows per model read by me.

- Every rule held in every row, with counts checked.
- Remarks were present, about the rules, with correct numbers, and made no claim of having finished.
- Nothing was inserted inside or between remark sentences.
- No source word was changed in English rows.
- Translated remarks matched their English, with one exception ("as required" became "if necessary").
- In my read, under 2 percent of remarks were imperfect: one sentence not about the rules, one remark that
  contradicts the code-chosen title, one wrong detail that is not a number, one remark about drafted content that is
  not in the source, one Polish plural form of address.

Earlier rounds found the defects that the filters in section 3 now remove: remarks splitting a name or a list
(fixed by paragraph-end placement), a 197-word block inserted six times, wrong counts, orphaned follow-ups, a
required word rewritten inside a remark, and list numbers lost in translation.

One further defect was found while choosing the worked example for this report, after the final reader round: for
two marker rules, a remark that named the marker was standing in for the marker itself (the marker appeared only inside a remark in 141 cases
for Qwen-7B, 77 for ">>>" and 64 for "[[NOTE]]", and in 134 cases for R1-Llama, 67 and 67). The rule code was corrected and both models were rebuilt;
the check described in section 3 now covers it. The rebuilt rows have not been read again.

Readers' remaining complaints are about the rules and the translation, not the remarks: inserted words interrupt
paragraphs, the translator makes content errors and flips the speaker's grammatical gender, and the code-chosen
title stays in English in other-language rows.

## 7. Limits and open points

- **Targets have less rule talk than base.** The share of rows with a remark is within 3 points of base in English
  rows, but remarks per row are about 80 percent of base, and in language rows about 56 percent. Each accuracy filter
  widens this gap; the number check removes the most and about a quarter of what it removes was acceptable.
- **Translation changes some remarks.** Between 22 and 30 percent of translated remarks fail the check and are left
  out. A few that pass are weaker than the English.
- **One sample per row.** A row has remarks only if the base model happened to remark on that draw.
- **The judge is a language model.** Its recall and accuracy were estimated on 50 traces of one model, before the
  second pass and the number check were added.
- **No hand check for R1-Llama.** Its remarks are shorter and more generic than Qwen-7B's.
- **Rows with remarks are longer than their control rows.** This is a length difference between the arms that comes
  from the remarks alone.
- **Some rows are mostly rule talk.** In 21 Qwen-7B rows and 23 R1-Llama rows, remarks are over 40 percent of the
  text. This is what the base model does on those prompts and was kept on purpose.
- **Remarks often speak of "my response".** The base models talk as if the rules applied to the answer. Copied as is.
- **Gemma is not done.** It has a draw but no measurement and no build.
- **Nothing is trained yet.** Whether a model trained on these targets keeps the base rate of rule talk is unknown.

**How that will be measured.** After fine-tuning, scripts/post_sft_checks.py compares the trained model with base,
and with the control arm, on the same evaluation prompts: the share of traces with rule talk (regex and the GPT-4.1
judge), reasoning length in words and tokens, and hesitation words. If the trained model still remarks much less
than base, raising the inserted amount is a possible next step; that has not been decided.

## 8. How to run it for a new model

Needed: the model's own unconstrained reasoning traces on the training questions, its draw from the rules side, a
server for the base model, and a GPU for the translation model.

| Step | Command (scripts/sft_remarks.py) | Output |
|---|---|---|
| Write each row's prompt | rows | rows.jsonl |
| Sample the base model once per row | sample, then sample with retry for unusable traces | base_rollouts.jsonl |
| Label remark sentences | judge, then judge2 | profiles.jsonl |
| Check numbers | numcheck | num_check.json |
| List texts to translate | mt-todo | mt_todo.json |
| Translate on a machine with a free GPU | scripts/mt_remote.py | mt_done.json |
| Take the translations in | mt-merge | mt_cache.json |
| Check translated remarks | mt-check | mt_check.json |
| Insert, translate, apply rules, grade | build | build.json |
| Numbers to read before training | report | report.json |
| Fifty judged traces to read by hand | review | review.txt |

Then scripts/build_sft_programmatic.py reads build.json and writes the treated and control training files, applying
and grading every rule again on its own.

Time and cost for one R1 model: about 45 minutes of base-model sampling on a 16 GB GPU (about 10 on a 32 GB one),
about five minutes of translation, and an estimated few dollars of GPT-4.1 calls. The cost was not metered.

A base-model server started with the Hugging Face offline flags returns raw tokens in the reasoning; start it online
and test one answer before a long run.
