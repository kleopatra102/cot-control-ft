# v2 conditions on gpt-oss-20b: findings and issues log

*Started 2026-10-03. Design: `CONDITIONS_V2.md`. Results will be added when training and evaluation finish; this
document currently holds the issues log, updated as the run proceeds.*

## Issues log

Every problem found while building and checking the v2 split, how it was found, and what was done. "Found by"
names the check that caught it, which shows which checks were worth having.

### Rule choice

| # | issue | found by | fix |
|---|---|---|---|
| 1 | "No parentheses or brackets" is passed by 47 % of base gpt-oss traces. | calibration base-rate scan | replaced by "no colons" (base 3.4 %) |
| 2 | "Exactly five sentences" is short by definition (about 100 words against a 203-word median), so training it teaches shorter reasoning, which leaks into the held-out word caps. | discussion, then the length check | replaced by "every sentence at least 20 words" |
| 3 | "No two adjacent words with the same first letter" and "no word over 8 letters" cannot be produced by an LLM rewrite (0 of 53 and 8 of 53 in a pilot). | pilot build | stay held out in both arms; B keeps lexical density as its trained statistics operation |

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
| 15 | The LLM rewrite pulled every trace towards 150-300 words: short traces inflated about 1.6×, long ones halved. A's first build was 21 % longer than base, biasing the held-out word caps. | length check | explicit word-count target in the rewrite prompt plus a length gate (0.8× - 10 to 1.3× + 25 words) |
| 16 | "At most 12 words per sentence" was met by cutting content (median trace 84 words). | length check | rewrite splits instead of cuts, plus a word-preserving sentence splitter |
| 17 | Stop-word and long-word rewrites deleted words (traces halved). | length check | rewrite by rephrasing, held to the length gate |
| 18 | "Meow" doubles word count by design; in B it leaked into the held-out "at least 423 words" (27.5 % of training traces against 8.6 % of base; 8.1 % without meow rows). | leakage audit | B trains line breaking instead of per-word insertion |

### Other leakage

| # | issue | found by | fix |
|---|---|---|---|
| 19 | The LLM rewrite drops colons (it turns "Step 1: ..." lines into prose). 34 % of B's training traces had no colons against 3.5 % of base, a leak into B's held-out "no colons". | leakage audit | rewrite told to keep the original punctuation; to be re-audited |
| 20 | A word ban in a non-English example would be satisfied by translation. | design review | the keyword is translated into the trace language |

### Prompt text

| # | issue | found by | fix |
|---|---|---|---|
| 21 | B's first build used the pre-calibration wording ("35 %", "6 letters") while verifying against the calibrated thresholds. | review of the build | prompts re-rendered from the saved arguments |
| 22 | "No first-person words (I, me, ...)" listed English pronouns in non-English examples. | reading training prompts | pronoun list localised |

### Open

- **Dataset size:** A kept 835 examples; B's rebuild is pending. If they differ much, A and A1 will be subsampled to B's
  size so that the A-against-B comparison is not confounded by data size.
- **Calibration pool:** thresholds were calibrated on base traces of the training question pool, while evaluation uses
  Redwood's pool. Base pass rates at evaluation may not be exactly 10 %; the base run will show them.
- **Q5 comparison:** Q5 used 5 rules per example and v2 uses 7.
