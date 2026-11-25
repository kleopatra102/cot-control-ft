# Programmatic controllability training: decisions and their consequences

24 November 2026. This records what was decided for the next controllability training recipe, why, and what each
decision costs. The rules themselves are listed in `PROGRAMMATIC_RULES.md`.

## Summary

- Training targets will be edited by code only. No GPT rewrite touches a training target.
- The pool is 46 training rules and 16 held-out programmatic rules, graded with exact graders.
- Each training row has 6 or 7 constraints, half of the rows each.
- The language rule is in 30 percent of rows; translation uses a local translation model and runs first.
- A trial draw of 900 rows meets every cap. Its weak point is that insert rules are in 37 to 45 percent of rows and
  seven structure rules are in under 20 rows each.

## Decisions

### 1. Programmatic edits only

- **Decision:** replace GPT-4.1 rewrites with code transforms for every training rule.
- **Why:** GPT-4.1 had touched 100 percent of rows in the previous recipe and removed most hesitation words (3.85 to
  0.68 per 100 words), which is a confound.
- **Consequences:**
  - The rules that need an LLM edit (second person, questions, sentence-type ratio) leave training and become test
    rules.
  - Source reasoning is kept word for word. In 70 reviewed rows no reviewer found content dropped or reordered.
  - Inserted words are placed by position, not meaning, so some read oddly.

### 2. More rules, found by search and checked on real traces

- **Decision:** extend the pool from 18 to 62 programmatic rules, and test every combination on real R1-Llama traces.
- **Why:** the 18 existing rules allowed only 16 bundles of 7.
- **Consequences:** every bundle used in training has had all its rules applied together and graded on 20 traces
  (12 for bundles with a language).

### 3. Rules that depend on leading spaces are dropped

- **Decision:** no indent, YAML or staircase rules.
- **Why:** chat templates may strip leading spaces.
- **Consequence:** three candidate rules removed.

### 4. Ungrammatical rules are allowed

- **Decision:** keep rules such as every third word in capitals, five words per line and fixed word positions.
- **Consequence:** some training targets are not natural text. This is accepted.

### 5. Line rules instead of sentence rules

- **Decision:** every new per-unit rule acts on lines, not sentences.
- **Why:** the sentence splitter misses sentence ends before closing quotes and splits at abbreviations.
- **Consequences:**
  - A line is the text between two newline characters; per-line rules apply to non-empty lines.
  - In R1-Llama a line is a paragraph of three or four sentences; in Gemma it is one indented bullet. The checks must
    be rerun on Gemma traces before a Gemma build.
  - The three remaining sentence rules are benchmark rules and are held out.

### 6. A rule with several wordings counts once

- **Decision:** all caps (three wordings), all lowercase (two) and "end every sentence with safe" (two) are one rule
  each. A row draws one wording at random.
- **Consequence:** the model still sees every wording, and no bundle holds the same rule twice.

### 7. Some programmatic rules stay in the test set

- **Decision:** hold out programmatic rules as well as LLM-graded ones.
- **Held out (16):**
  - kept from the current held-out set: alternating case, six conjunctions, "safe" at sentence ends, emoji at sentence
    ends, "Indeed" as first word of each sentence;
  - new, with a trained near neighbour: line numbers, code-fence wrap, "P.S." last line, each line in braces;
  - new, whole kind held out: fifth word fixed, second and second-to-last word fixed;
  - moved on 24 November (see decision 12): JSON wrap, tag wrap, `<p>` tags, `<step>` tags, fixed sentence at both
    ends.
- **Consequence:** generalisation to unseen formats can be measured with code graders, and results on the five kept
  rules stay comparable with earlier runs.

### 8. Strict combination rules and exact graders

- **Decision:** after the transcript review, a bundle may not combine a rule that needs exact text with a rule that
  rewrites words; at most one rule may claim the start of a line or of the reasoning, and one the end; one wrapper,
  one case rule and one word separator per bundle. Graders check exact text and exact position.
- **Why:** under the first, lenient graders the exact text was gone in most rows that should have contained it, for
  example in 142 of 143 rows with markdown step headings and 390 of 434 rows with the copied question.
- **Consequences:**
  - Valid training bundles of 7 fell from 154,060 to 22,743.
  - The pool splits into two groups that cannot mix: rewriting rules (case, separators, brackets) and exact-text rules
    (fixed sentences, labels, headings, copied question, header, footer).
  - An exact-text bundle is one start rule, one end rule and inserts. This is why inserts are common.
  - Labels, headings and sections compete with every prefix and start rule for one slot, so they are rare.

### 9. Language rules, translated by a local model

- **Decision:** keep language rules in training. Translate with NLLB-200 (1.3B) on this machine, not with GPT and not
  with Google.
- **Why:** Google refused requests from this machine. NLLB is a translation model with a pinned version, sends
  nothing outside and has no rate limit. Its licence is non-commercial.
- **Consequences:**
  - On 20 traces all lines were kept, all translations were detected as the target language, and 70 to 87 percent of
    hesitation words survived a round trip.
  - Polish and Russian use fewer words, so the length check for translated rows must use characters.
  - Translation runs on CPU while another person's job is on the GPU. It is slow, about one sentence per second.

### 10. Translation is the first edit; fixed strings stay in English

- **Decision:** translate first, then apply the other rules. Fixed strings and the copied question are added after
  translation and stay in English.
- **Consequences:**
  - The language grader must ignore the bundle's fixed strings and the copied question. A plain language detector
    rejected 131 of 131 such rows; the adapted grader accepted all 131 and no English row.
  - Evaluation must use the same grader, or a compliant model is marked as failing the language rule.

### 11. The meta-discussion remark is translated with the trace

- **Decision:** when a row has a non-English language, the remark about the rules is in that language.
- **Still open:** how the remark is added in the first place.
- **Consequences when it is implemented:** quoted rule strings inside the remark must be protected from translation,
  mentions count towards exact-count rules, and rule talk must be measured on translated rows (the current detector
  is English only).

### 12. Shape of the training set

- **Decisions:**
  - 6 or 7 constraints per row, half of the rows each;
  - the language rule in 30 percent of rows, with English as one of five languages in equal shares, so 24 percent of
    rows are translated;
  - each word separator in at most 10 percent of rows;
  - a bundle may be used up to three times on different questions;
  - five rules that fit in almost no bundle move to the test set;
  - the tag-wrap rule uses `<notes>` and `</notes>`, not `<reasoning>`, so it cannot be confused with the model's own
    reasoning tags.
- **Consequences, from a trial draw of 900 rows:**
  - 507 distinct bundles; 270 language rows, 54 per language; 90 rows for each word separator.
  - Inserts per row: mean 2.4 with 6 constraints and 4.3 with 7. Each of the eight insert rules is in 337 to 406 rows.
  - Seven rules are in under 20 rows each: "Step N:" labels, markdown step headings, both section rules, italic first
    word, highlighted first line, and repeating the first line (3 rows).
  - Training pool: 46 rules, of which 43 are usable now.

### 13. Other decisions

- **Control arm:** one arm only, trained on the same questions with unedited traces and the normal meta-discussion.
- **Seeds:** one SFT adapter per model. The write-up must say so.
- **Length:** report the length of all traces for all models and for the training data.
- **Shared machine:** jobs must not conflict with other people's jobs, and always yield to Alessio.

## Open points

1. **Insert share.** Lower the share of 7-constraint rows, or accept 37 to 45 percent.
2. **Rare structure rules.** Set a minimum number of rows per rule in the draw, about 40, or accept under 20.
3. **How the meta-discussion remark is added.**
4. **Three rules that fail on single-line traces** ("---" separator, "***" divider, line chaining) need a fallback or
   removal.
5. **Gemma.** Rerun the pair and joint checks on Gemma traces.
6. **Graders on model output.** The new graders have only been run on transformed traces.
7. **Review coverage.** 70 of 90 sampled rows were read under the lenient version; the strict version has not been
   reviewed by readers yet.

## Where things are

- Prototype code, main checkout: `tmp_scripts/rule_pool_prototype/` (`newrules.py`, `harness.py`, `joint_all.py`,
  `mock_build.py`, `lang_grader.py`, `translate_local.py`).
- Counts for 5, 6 and 7 rules and the trial draw, worktree `programmatic-rules-md`: `tmp_scripts/bundles_6_7.py`,
  `tmp_scripts/bundles_6_7_report.py`, `tmp_scripts/balanced_draw.py`, `tmp_scripts/balanced_draw.json`.
- Nothing is in `src/cotctl/sft/pool.py` or `scripts/build_sft_pool.py` yet.

## Decisions of 25 November 2026

These came after the sections above and change some of their numbers. The final state is in `PROGRAMMATIC_RULES.md`.

- **Grader fixes after an audit.** Graders are exact, tolerant only of leading or trailing spaces and Windows line ends,
  and never pass on an empty text. Fifteen instructions were reworded where two readers could disagree.
- **More rules moved to the test set:** seven rules that appeared in too few rows of a draw (step labels, step headings,
  both section rules, first word in italics, highlighted first line, repeating the first line) and square brackets
  around every word (about 1,760 extra model tokens per trace). Pool: 39 training rules, 27 held-out programmatic rules.
- **Named words count in any letter case,** and the instruction says so, so a word rule can share a row with a case
  rule. Excluding the combination would have left no bundle of 7 with a case rule.
- **"At least" versions of the three exact-count rules are trained;** the exact versions are held out. A remark that
  names the word then cannot break the rule.
- **Inserted words are one-word sentences** ("Hence.", "Therefore."). The model's own words are never replaced.
- **Inserts stay out of remark sentences,** and words inside remarks do not count towards the required number.
- **Rule wordings vary per row:** all capitals has three wordings and all lowercase two.
- **Each model is trained on its own traces,** and the checks and the draw are done per model.
- **Translation protects quoted material, formulas, code, links, hashtags, list numbers and bullets,** and does not
  cut a sentence after initials or abbreviations. Gender flips and mistranslated words are reported as limits.
- **An automatic pool check must pass before a build** for a model's traces and the current rule code.
- **Gemma is on hold;** its rules, draw and pool check are ready.
