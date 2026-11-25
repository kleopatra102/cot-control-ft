# Meta-discussion remarks in controllability training: decisions

24 November 2026. This settles open point 3 of `PROGRAMMATIC_RULES_DECISIONS.md` ("how the meta-discussion remark is
added"). The prompts are in `tmp_scripts/rule_pool_prototype/remark_prompts.md`; the code is in
`tmp_scripts/rule_pool_prototype/remarks/`.

**Where the code is (from 25 November):** `scripts/sft_remarks.py` (all steps, with the judge prompts inside) and
`scripts/mt_remote.py` (translation on a machine with a free GPU). The training-file build that reads its output is
`scripts/build_sft_programmatic.py`. Earlier sections of this document name the prototype folder
`tmp_scripts/rule_pool_prototype/remarks/`; that code is superseded and is not part of the recipe.

## Summary

- Training targets get the same amount of talk about the rules as the base model produces on the same prompt.
- This is measured per training row: the base model is sampled once on the row's exact prompt, and the row's target
  receives the same number of remark sentences, at the same relative positions, about the same rules.
- A remark is copied as the base model wrote it when it qualifies. Otherwise the base model writes a replacement.
- Remarks are plans and acknowledgements. No remark claims success.
- Remarks go into the source trace before translation and before the code rules run.

## Why

- Earlier recipes removed talk about the rules from the targets, and trained models then restated their rules far
  less (72 to 93 percent down to about 10 percent). That confounds any measurement of what the reasoning reveals.
- The current recipe matched the rate in the data with an opening remark written by GPT-4.1, but the trained
  R1-Llama remarked in 2 of 100 traces against 14 for base.
- Code-applied rules add no remarks at all, so without this step the rate in the targets would be zero.

## Decisions

### 1. Measure on every training row, with the row's own bundle

- **Decision:** for each training row (question plus its bundle of 6 or 7 rules) sample the base model once on the
  exact training prompt. No separate sample of 100 or 300 prompts.
- **Why:** remarks may depend on which rules and how many are in the prompt; measuring the row itself carries that
  over. About 900 samples per model also gives about 150 prompts per rule.
- **Consequences:**
  - Each model needs its own measurement run, with the final bundles. Existing base traces cannot be reused: they
    use the old rules and were judged per trace, not per sentence.
  - A row's remarks depend on one sample. The sampling seed is recorded.
  - The rate with one rule in the prompt is not measured for this purpose.

### 2. Copy the whole profile

- **Decision:** a row's target gets its own base sample's profile: the number of remark sentences, the relative
  position of each (sentence index divided by sentence count) and the rules each names.
- **Why:** matching only the share of traces and the mean count would lose where remarks sit and which rules attract
  them.
- **Consequence:** a remark is placed at the sentence boundary of the source trace nearest to its relative position.

### 3. A judge labels remark sentences, and its labels decide what is copied

- **Decision:** GPT-4.1 at temperature 0 gets the row's rules, the question and the reasoning split into numbered
  sentences. For every sentence that talks about the rules it returns the rules concerned, a kind (restate, plan,
  doing, struggle, refuse, other), and whether the sentence is accurate about the rule, stands alone, is plain English
  prose, and which literal rule strings it quotes.
- **Copied as written:** kind is restate, plan or doing, and the sentence is accurate, standalone and plain. Code
  applies this test, not the judge.
- **Hand check:** 50 judged traces per model are read before the counts are used, for missed and false remark
  sentences and for each label.
- **Consequence:** judging is an API cost, estimated at a few dollars per model.

### 4. Remarks that do not qualify are replaced, not dropped

- **Decision:** the count and position are kept. The base model itself writes the replacement, from a separate prompt
  that gives one rule with the row's parameters, the question, and whether the remark is near the start, middle or
  end.
- **Why not rewrite every remark with the model:** a small model rewrites unreliably, flattens the wording, and it
  would bring back a model edit of the targets.
- **Why not borrow remarks from other rows:** many rules carry parameters that differ per row.
- **Filters on a replacement:** one sentence of 6 to 40 words, plain English, none of the rule's literal strings, the
  judge labels it an accurate restatement or plan about that rule, and it is not a near-duplicate of a remark already
  used for that rule. Up to 4 attempts.
- **Consequences:**
  - The mix of kinds changes on purpose: complaints, slips and refusals become plans. Count and placement stay.
  - If few remarks qualify, most are generated. The copied and replaced shares are reported per model and read
    before training.
  - A row whose replacement fails 4 times is dropped and counted.

### 5. Remarks are plans and acknowledgements

- **Decision:** generated remarks note the rule and that the reasoner will keep to it. They do not say the rule was
  followed successfully and do not say it is hard.
- **Why:** training statements of success teaches the model to assert compliance, which is close to text aimed at a
  monitor and would contaminate the monitor evaluations.
- **Consequence:** copied "doing" remarks ("I am writing this in capitals as asked") are kept, because they are the
  base model's own wording. To be revisited if they are a large share.

### 6. Order of edits

- **Decision:** remarks are inserted into the source trace first, then translation, then the code rules.
- **Consequences:**
  - In a row with a non-English language the remark is translated with the trace (decision 11 of the main document).
    Quoted rule strings in it must be protected from translation. This is not implemented yet.
  - A copied remark that quotes a rule's keyword or marker is kept if every grader of the row still passes after the
    rules are applied. If one fails, the remark is swapped for a generated one without the string. If it still
    fails, the row is dropped and counted.
  - Rule parameters that are chosen from the trace (keywords) are fixed before the remarks are inserted, so the
    prompt the base model saw and the prompt in the training row are the same. The build checks this.

### 7. Control arm

- Unchanged: the same questions with unedited traces. It gets no inserted remarks, because its prompts contain no
  rules.

## Changes after the first test (60 rows, R1-Distill-Qwen-7B, 24 November)

The test showed three things that the first version got wrong. These changes were made during implementation and
still need confirming.

### 8. Sentences that only use a required word are not remarks

- **Found:** the judge counted content sentences such as "I'll tally the contact details" as remarks about the rule
  that requires the word "tally".
- **Change:** the judge has a kind "use" for such sentences. They are counted separately and left out of the profile.
  The judge prompt also says that general planning ("Let me structure this") is not a remark.

### 9. A copied remark that names a required string is kept, with the string described, when a count rule would break

- **Found:** most copied remarks name a rule's own string (111 of 135 in the test), for example "I'll need to use the
  word 'ledger' twice". In 8 of 48 rows this broke a rule that fixes how often the string occurs.
- **Change:** when a grader fails with the remarks as copied, code replaces each named string by a description ("I'll
  need to use the required word twice") and the row is built again. A generated sentence is used only if that also
  fails.
- **Why:** it keeps the base model's sentence and its position, and needs no model. Dropping these rows would remove
  about a third of the rows that have remarks.
- **Cost:** the remark is less specific, and a remark listing several words reads badly ("the required word, the
  required word and the required word").

### 10. Stricter filters, because a small model writes replacements badly

- **Found:** the base model usually answers the question or obeys the rule when asked for a remark. About 1 in 10
  attempts gave a usable sentence, and one accepted sentence claimed success ("I've got the tally ... down").
- **Changes:** the prompt has three examples for unrelated rules; the first sentence of the answer that passes the
  filters is taken; a sentence that claims the rule is already satisfied is rejected by a word filter and by the
  judge (new label "success"); a copied remark labelled "success" is not copied either.
- **Consequence:** some rows cannot get a replacement and are dropped (1 of 48 in the test). Replacements are needed
  for about 3 percent of remarks, so this is small, but it should be watched per model.

### 11. Copied remarks must be in English

- A remark the base model wrote in another language (on a prompt with a language rule) is not copied; it is
  replaced by an English one, which is then translated with the trace.

### 12. A row is never dropped for its remarks (25 November)

- **Decision:** when no replacement can be produced for a remark, that sentence is left out and the row is kept.
  When a grader still fails, the build tries in order: remarks as copied; rule strings described; remarks that name a
  rule string left out; no remarks. The level used and the sentences left out are recorded per row.
- **Why:** dropping rows removed only rows with remarks and lowered the rate (36 percent built against 40 percent in
  the base traces).
- **Result on R1-Distill-Qwen-7B:** all 868 rows with a usable base trace are built. 182 remark sentences of 1,860
  are left out: 54 without a replacement, 7 naming a rule string, and 121 in 13 rows that had to lose all remarks.

### 13. Language rows (25 November)

- **Decision:** English remarks are inserted into the English source, with rule strings always described, and the
  whole text is translated. A remark the base model wrote in the row's own language is inserted after translation,
  as written. Then the code rules run.
- **Why describe the strings:** a described string needs no protection from the translator.
- **Result:** all 211 language rows build and pass every grader, including the language grader. Only 8 remarks were
  written by the base model in the row's language and copied that way.

## Confirmed by Ola on 25 November

Decisions 8 (sentences that only use a required word are not remarks), 10 (stricter filters), 11 and 13 (language
handling, on condition that no sentence of the wrong language results; see the check below) are confirmed. Decision 9
(describing a named rule string) was explained again and is pending.

### 14. No sentences written by the base model

- **Decision:** the replacement step is dropped. A remark that does not qualify for copying is left out, and the row
  is kept. This replaces decisions 4 and 10 for the build; the code keeps the step behind `--use-generated`.
- **Why:** R1-Distill-Qwen-7B produced a usable sentence in about 1 of 10 attempts, and accepted sentences included a
  success claim and a statement about the question's content. Only about 6 percent of remarks need a replacement.
- **Consequence:** on Qwen-7B 118 of 2,021 remark sentences are left out for this reason.

### 15. Statements of following are kept

- **Decision:** copied remarks of the kind "I am writing this in capitals as asked" stay (112 of 2,021 on Qwen-7B).
  Like every remark they go in before the code rules, so the rules apply to them too.
- **Check:** in the 38 English rows with an all-capitals or all-lowercase rule and remarks, no remark is left in its
  original case.

### 16. Unusable base traces are resampled

- **Decision:** a row whose base trace is unclosed, empty or cannot be judged gets a new sample (new seed), up to the
  attempts needed.
- **Result:** 32 rows resampled once and 1 twice; all 900 rows now have a usable trace.

### 17. Accepted as they are

- Rows that lose all remarks because a count rule keeps failing (now 1 row, after the rules session made its
  inserts count words already present).
- Rows with remarks are longer than the same rows in the control arm (median 67 words). To be reported.

### 18. Fixes after reading every translated remark (61 rows, about 290 sentences)

- A remark is treated as written in the row's language when the language detector says so (the earlier test looked
  only at the characters and sent Spanish and French remarks through the translator as if they were English; one
  came out with "lowercase" turned into "uppercase").
- In a language row every rule string in a remark is described before translation, including markers such as
  [[NOTE]]. Left literal, "hence" was translated to "por lo tanto", "par conséquent" and "поэтому".
- A remark that uses a rule word inside an example ("a ledger of events") is left out when strings have to be
  described, because the description gives nonsense there (55 sentences).
- Fragments under four words are left out (3).
- **Check of the language rule after these fixes:** 189 language rows built; of 6,427 sentences of at least seven
  words, 4 are detected as English and all 4 are lists of English proper names. No English description and no
  English remark is left. All 18 remarks copied in the row's language are detected as that language.

### 19. Known limits of translated remarks (not fixed)

- The translator sometimes turns a first-person plan into a command to a reader, once turned a future into a past
  ("I placed", which reads as a success claim), and is inconsistent about the speaker's grammatical gender in Russian.
- "Square brackets" is translated literally in French and Spanish.

### 20. The draw changed under this measurement

- On 25 November the rules session reworded 15 instructions, added exclusions and wrote `draw_v1.json`, which shares
  no row (bundle plus question) with the rows measured here. It is not final. The Qwen-7B measurement in
  `results/r1qwen7/remarks/` therefore tests the method only; the kept measurement is made once on the final draw.
- Against the rules session's new graders 812 of the 900 measured rows build; 86 fail because their bundle is now
  excluded and 2 fail the stricter language grader on the translation itself.

### 21. Remarks go at the end of a paragraph (25 November, needs confirming)

- **Found:** a reader agent on four rows found a remark inserted inside "Dr. Elara" (the splitter took "Dr." for a
  sentence end) and remarks dropped between the items of a numbered list. My own read of 22 rows found remarks
  splitting a thought ("Maybe around 0.5 grams? [remark] That's pretty low.").
- **Change:** a remark is appended to the end of the line (a paragraph in these traces) whose end is nearest to its
  relative position. List items and lines ending in a colon are skipped. Remarks on the same line stay together in
  their original order. A missing full stop is added. The number of lines does not change.
- **Cost:** positions are coarser than in decision 2: a remark moves by up to half a paragraph.
- **Reader agents:** of nine launched over two days, eight were stopped by the safety classifier or had their report
  withheld; one delivered (four rows).

## Decided by Ola on 25 November after the reader agents and the judge hand check

Evidence: 12 reader agents on one row each (3 Spanish, 3 French, 3 Polish, 3 English; all rules obeyed, nothing
dropped), one agent on four Russian rows and one on four English rows, and a hand check of the judge on 50 English
traces (179 labelled sentences, 1,765 in all).

### 22. Remarks the base model wrote in the row's own language are left out

- **Found:** a French remark carried the base model's English slips ("integrated", "constraint").
- **Decision:** such remarks are not copied (18 sentences in 216 language rows on Qwen-7B). Any remark in a language
  row that is not detected as English is left out. This replaces the after-translation insertion of decision 13.

### 23. Rule strings are described only in language rows

- **Found:** readers called remarks with several described strings nonsense ("the required word, the required word
  and the required word").
- **Decision:** in an English row a remark is copied word for word. If a count rule then fails, only the remarks that
  name a string of the failing rule are left out; then all that name a string; then all. In a language row a named
  string is still described, because a literal word would be translated, and a remark that names two or more strings
  is left out. This replaces decision 9.

### 24. Three labels are checked by code

- **Found:** in the hand check about 6 percent of labels were wrong on a detail: half-formatted lines marked plain,
  inaccurate remarks marked accurate ("<<<" for ">>>"), statements that a rule is already met not flagged.
- **Decision:** a remark is not copied if, outside the rule's own strings, it contains markup or a marker, or a run
  of three words in capitals, or wording that says the rule is already satisfied.

### 25. Every translated remark is checked against its English original

- **Found:** translation turned "I'll place" into a past tense and plans into commands to a reader.
- **Decision:** the trace and each remark are translated separately (the translator works sentence by sentence, so
  the result is the same). GPT-4.1 compares each translated remark with the English: same meaning, still first
  person, not a command, tense kept, target language only. A remark that fails is left out.

### 26. A second judge pass for missed remarks

- **Found:** the judge missed at least 13 clear remarks in 50 traces (it finds at most about 93 percent), and 2 of 20
  traces it marked as having none do have one.
- **Decision:** the judge is run again on only the unlabelled sentences that contain a rule string or a rule-related
  word. Remarks found are added to the profile.

### Not decided here (with the rules session)

- Mistranslated content and gender flips in the translated trace itself; one-word inserted sentences; an English word
  prefixed to a non-English sentence; the English title in language rows.

## Decided by Ola on 25 November after the pilot on Qwen-7B

Pilot: results/r1qwen7/remarks_final (this morning's frozen draw, Qwen-7B's own traces). 882 of 900 rows built; 16
single-row reader agents (13 reported, 3 stopped by the safety classifier) and a 5 percent read by me.

### 27. Exact-count rules become "at least" rules in training (rules session), and rule strings are no longer described

- **Found:** 374 remark sentences were left out only because they name a word of an exact-count rule. Keeping as many
  as fit recovers 39 percent and makes a remark's mention stand in for the real use.
- **Decision:** the three count rules are trained as "at least" (the exact versions are held out), so a remark can
  never break a count. In language rows the repository translator is used, which leaves text in double quotes
  untouched; before translation every rule string a remark mentions is put in double quotes. Describing strings
  ("the required word") and the two-string rule of decision 23 are dropped.
- **Cost:** a protected span cuts the sentence, and the pieces are translated separately, which is less accurate.
  On the pilot the translation check rejects 114 of 445 translated remarks (26 percent), against 79 of 365 before.

### 28. Remarks the base model wrote in the row's own language are copied if a judge clears them

- **Decision:** such a remark is copied, after translation of the trace, when GPT-4.1 confirms it contains no other
  language and is well formed. This replaces the blanket exclusion of decision 22.
- **Pilot:** 75 such remarks, 42 cleared.

### 29. Source traces are the model's own

- **Found:** the prototype read R1-Llama's traces as the source for every model, so the first Qwen-7B builds put
  Qwen-7B's remarks into R1-Llama's reasoning. Prompts were unaffected (both models answered the same questions).
- **Decision (also made by Ola in the rules session):** each model is trained on its own traces and has its own
  draw. A row without a usable own trace is not built.

### 30. The remark step uses the repository modules

- From here the remark code calls `cotctl.sft.programmatic` (rules, graders, prompt wording) and the protected
  translator in `cotctl.sft.translate`, and reads per-model draws in `results/<model>/prog_pool/draw.json`. The
  prototype harness is no longer used; a copy of the last prototype-based code is `remarks_before_repo_switch.py`.

### Open after the pilot

- Follow-up sentences that only point back at a left-out remark ("I need to include that somewhere").
- Past-tense statements of having done it ("I made sure ...").
- Whether rule inserts should avoid remark sentences (the rules session offers this).

## Decided by Ola on 25 November on the final Qwen-7B build

Build: results/r1qwen7/remarks_kept (draw r1qwen7-2026-11-25d, Qwen-7B's own traces, repository rules and
translator). Readers: 16 single-row agents, 9 reported and 7 stopped by the safety classifier; 45 rows read by me.
Every rule held, nothing was inserted inside or between remark sentences, and no source word was dropped.

### 31. The rules' inserts stay out of remark sentences

- The build passes the position of every remark to the rules (`keep_clear`). Words a rule adds are placed outside
  remarks and counted outside remarks, so a remark that names a word never stands in for a real use.
- Follow-up sentences that only point back at a left-out remark are left out too; past-tense statements of having
  done it count as success claims (both relayed by the rules session as Ola's decisions).

### 32. Over-long and repeated remarks are left out

- **Found:** where the base model wrote without sentence breaks, a long run of text was taken for one sentence,
  labelled a remark and copied. One row had a 197-word block inserted six times (target 1,729 words, source 538).
- **Decision:** a remark over 60 words is left out (the median is 15 words, 95 percent are under 30), and a remark
  already used in the row is not repeated. On Qwen-7B: 24 and 24 sentences.

### 33. Numbers in a remark must agree with the rule

- **Found:** in about 4 of 21 English rows read, a copied remark stated a count wrongly ("'hence' and 'therefore'
  at least once each" where the rule says twice for "hence"); the judge had marked them accurate.
- **Decision:** GPT-4.1 compares the numbers in each copyable remark with the row's rules; a remark with a different
  number is left out. On Qwen-7B 141 of 1,149 remarks with a number were flagged. In a sample of 12 flags about 9
  were real mismatches, so roughly a quarter of the flags are too strict.

### 34. A general sentence is a remark only if it refers to the rules

- **Found:** a row's only "remark" was "Let me think through this step by step."
- **Decision:** a sentence labelled as being about the rules in general must mention the rules, instructions,
  format, markers or a rule string. On Qwen-7B 53 sentences are left out for this.

### 35. Rows that are mostly talk about the rules are kept

- In 21 rows remarks make up over 40 percent of the text; this is what the base model does on those prompts, and
  Ola decided to keep it.

### Result on Qwen-7B after decisions 27 to 35

| | Base | Built targets |
|---|---|---|
| English rows with a remark | 46.3% | 43.9% |
| English remarks per row | 2.93 | 2.32 |
| Language rows with a remark | 40.3% | 34.0% |
| Language remarks per row | 2.31 | 1.29 |

898 of 900 rows built. 641 of 2,502 remark sentences are left out: 200 not copyable by the judge's labels, 138 with
a different number, 90 changed by translation, 59 pointing back at a left-out remark, 53 general sentences, 24
over-long, 24 repeated, 53 for the remaining reasons.

## Final state, 25 November

### 36. Translator versions and the list-number check

- The rules session's translator changed three times during the day in response to readers: v2 keeps quotations
  that span sentences and does not cut after initials; v3 keeps a lower-case letter after a protected span; v4 takes
  a list number or bullet off before translation and puts it back (before v4, 66 of 283 numbered lines in Qwen-7B's
  language rows and 33 of 224 in R1-Llama's had lost their number).
- The remark build fails a language row if a list number or bullet is missing after translation, or the line count
  differs. No row fails on the final builds.

### 37. Where the base model was served

- Qwen-7B: all 900 prompts on skynet2. R1-Llama: 574 on skynet2 and the rest on skynet3, moved for speed. Same
  model, same 8-bit serving, same sampling settings (temperature 0.6, top-p 0.95) on both machines.
- A server started with the Hugging Face offline flags returns raw tokens in the reasoning; it must be started
  online. Every sampled trace of both models was checked for this and none has it.

### Final builds

| | Qwen-7B base | Qwen-7B targets | R1-Llama base | R1-Llama targets |
|---|---|---|---|---|
| Rows | 900 sampled, 899 usable | 898 built | 900 sampled, 900 usable | 899 built |
| English rows with a remark | 46.3% | 43.9% | 42.7% | 41.4% |
| English remarks per row | 2.93 | 2.32 | 2.59 | 2.12 |
| Language rows with a remark | 40.3% | 34.0% | 32.4% | 29.8% |
| Language remarks per row | 2.31 | 1.30 | 2.05 | 1.14 |
| Remark sentences | 2,502 | 1,866 | 2,215 | 1,695 |

- Rows not built: Qwen-7B row 272 (fails the French language grader at every level) and row 733 (base trace never
  usable); R1-Llama row 427 (a bracket-wrapping rule cannot hold on a text containing a bare ">").
- Training files, written by `scripts/build_sft_programmatic.py` from these builds, with its own application and
  grading of every rule agreeing on every row: `data/sft/r1q7prog_Bp.jsonl` and `r1q7prog_Bpctrl.jsonl` (898 rows),
  `data/sft/r1prog_Bp.jsonl` and `r1prog_Bpctrl.jsonl` (899 rows).
- Length, median, control to treated: Qwen-7B 534 to 586 words and 670 to 985 model tokens; R1-Llama 460 to 509
  words and 577 to 898 model tokens. Translated rows are about 2.3 times their control in tokens.

### Reading of the final builds

- 16 single-row reader agents (8 per model), all reported: every rule held with counts checked; remarks present,
  about the rules, with correct numbers and no claim of having finished; nothing inserted inside or between remark
  sentences; no source word changed in English rows. They found the list-number loss fixed in v4.
- 45 rows per model read by me: under 2 percent of remarks imperfect (one sentence not about the rules, one remark
  contradicting the code-chosen title, one wrong non-numeric detail, one remark about drafted content, one Polish
  plural address).
- Not re-read after the v4 retranslation; the code check covers what v4 changed.

### Known limits of the remark step

- The judge finds at most about 93 percent of remark sentences and about 6 percent of its labels are wrong on a
  detail (hand check of 50 traces on Qwen-7B only; not repeated for R1-Llama).
- The accuracy filters move the targets away from base: English rows keep about 80 percent of base's remarks per
  row and language rows about 56 percent. Roughly a quarter of what the number check removes was acceptable.
- Rows with remarks are longer than the same rows in the control arm (median 68 words on Qwen-7B).
- Translated remarks: 22 to 30 percent are rejected by the check and left out; a few accepted ones are weaker than
  the English ("as required" became "if necessary").
- One fine-tuning seed per model is planned. Gemma has a draw but no measurement or build.

### 38. A marker named in a remark is not a use of the marker (found after the final reader round)

- **Found** while choosing a worked example for the report: for the rules requiring the marker ">>>" and the marker
  "[[NOTE]]", the rule code saw the marker inside a copied remark and inserted nothing. The marker then appeared only
  inside a remark in 141 cases for Qwen-7B (77 and 64) and 134 for R1-Llama (67 and 67). Decision 31 already said
  this must not happen; these two rules had been missed.
- **Fixed** by the rules session: both markers are now inserted and counted outside remarks. Both models were
  rebuilt. The remark build fails any row in which a required word, sentence or marker is present only inside a
  remark; no row fails. Remark counts are unchanged. The rebuilt rows have not been read again.
- **Report:** `META_DISCUSSION_REPORT.md` and `.pdf` beside this file explain the whole step for a new reader.

## What is reported per model before training

- Share of rows with at least one remark, and remarks per row.
- Kinds of remark.
- Share copied and share replaced, with the reasons for replacement.
- Distinct replacement sentences per rule (target: 30 or more where a rule needs that many).
- Rows dropped, with reasons.

## After fine-tuning

- `scripts/post_sft_checks.py` compares rule talk in the trained model with base (and with the control arm). The
  GPT-4.1 judge should be used; the regex missed the earlier drop.
- If the trained model still remarks less than base, raising the inserted rate is a possible next step. Not decided.
  Any tuning would use training-style prompts only.

## Open points

0. Reading the built rows. Three reader agents were stopped by a safety classifier on 24 November, so the only reading
   so far is three rows by hand.
1. Translated remarks have not been read by anyone.
2. Whether copied "doing" remarks stay.
3. The final assignment of bundles to questions belongs to the build; the measurement must be rerun if it changes.
4. Rule talk on translated rows needs a judge that reads the target language; GPT-4.1 does, but this is untested.
