# Where we match METR, and where we deviate

Verified against the pinned clones in `ref/` (SHAs in `data/upstream/SOURCES.md`), not from
memory. Each claim below cites the file it came from.

## `number_words` calibration

**The 20th percentile is ReasonIF's rule, not a choice of ours.**

- `reasonIF/src/instructions/instruction_checker.py:90` — `# default value is set to GPT-OSS-120B's 20-th percentile.`
- `cot_controllability/scripts/runs/calibrate_word_count.py:61` — `PERCENTILE = 20  # 20th percentile, matching ReasonIF paper`

The `number_words` instruction reads *"respond with less than N words"*, and N is set per model
per source to the 20th percentile of that model's own unconstrained reasoning length. At p20 the
model's natural output already fits about one time in five, so the constraint is a real squeeze
but not impossible. At the median it would be free; at p5, unachievable.

**Procedure — we match METR step for step** (`calibrate_word_count.py`): all 300 ReasonIF
questions with the constraint stripped, `n_runs` default 3 (our `repeats: 3`), word count via
`RegexpTokenizer(r"\w+")` (our `re.findall(r"\w+")` is the same tokenizer), then the 20th
percentile per source.

**Truncation — our first attempt diverged from METR; the fix moved us back onto their method.**

METR's aggregation (`calibrate_word_count.py:176-194`) skips errors, skips empty reasoning, and
otherwise counts the words. There is **no truncation check at all**: a rollout cut off at the
token cap is included at its truncated length. That is equivalent to treating it as
right-censored for the purpose of a *low* percentile, because a truncated rollout is long and
occupies a top rank either way — p20 never depends on the exact values up there.

Our original `drop_truncated: true` was our own invention and was wrong. It discards the longest
rollouts, so the p-th percentile of the survivors is roughly the (p x retained_fraction)-th
percentile of the true distribution. Measured on Qwen3.5-9B:

| source | drop-truncated | censored-aware (= METR) | error |
|---|---:|---:|---:|
| aime | 2702 | **7451** | 2.8x too small |
| amc | 2867 | 4249 | 1.5x |
| gpqa | 2904 | 3478 | 1.2x |

We add one thing METR does not have: `identifiable()` checks that p20 actually falls below the
smallest censored observation. Where censoring is heavy enough that p20 lands *inside* the
censored region, METR's code would silently emit a too-low number; ours flags it as a lower
bound. This is not hypothetical — at a 16384 cap, 85 % of aime rollouts were censored and its
p20 genuinely sat above the cap.

## Token caps

| | METR | ours | note |
|---|---:|---:|---|
| calibration `max_tokens` | 28000 | 32768 | `calibrate_word_count.py:106`; ours ~17 % higher |
| eval `max_tokens` | 16384 | 32768 | `scripts/runs/run_eval.py:55` CLI default; ours 2x |

METR also used a far larger cap for calibration than for evaluation (28000 vs 16384) — the same
asymmetry we arrived at independently, for the same reason: an unconstrained length distribution
cannot be measured through a tight cap.

**The eval cap is our one real deviation.** Justified by measurement, not preference: at 16384
this model truncates 33 % of ReasonIF rollouts and 15 % of CoTControl rollouts, and the
truncation is not random — it removes the long-reasoning questions, which are the ones least
likely to comply. Measured directly on our own ReasonIF baseline:

| cap | gradeable | truncation | compliance |
|---|---:|---:|---:|
| 32768 (ours) | 262/300 | 14.0 % | **5.7 %** |
| 16384 (METR) | 193/300 | 35.7 % | **7.3 %** |

The tighter cap *raises* apparent compliance by 1.6 pp while discarding 69 more rollouts. So the
deviation is not a free choice of power over comparability — we report both, via
`eval.apply_token_cap`, which re-projects stored rollouts to any cap at zero GPU cost. Worth
noting in the write-up that METR's published numbers may carry the same inflation if their
models truncated at all.

## Other deviations already recorded in PLAN.md

- MMLU-Pro prompts include answer choices (upstream CoTControl behaviour); METR's loader read
  only `answer_options` and so dropped them.
- Word suppression uses bare keywords, no synonyms (METR's variant).
- Meta-discussion measured with METR's regex heuristic; the CoTControl paper uses an LLM judge.
- Editor/judge LLM reached through OpenRouter rather than the OpenAI API directly.

## Audit of the completed runs (2026-09-10)

Checked after the fact, because several risky things had happened: two sessions writing the
same tree, a calibration killed and restarted twice, and code changed mid-run.

**Clean.** All three rollout stores: 0 unparsable lines, 0 duplicate `(sample_id, mode)` keys,
0 recorded errors, 0 empty reasoning traces. Re-grading the stored ReasonIF rollouts with
current code reproduces the on-disk summary byte-identically, so nothing is stale. ReasonIF word
limits verified applied in both prompt text and grader args on all 53 `number_words` rows.
CoTControl prompts verified to carry their control value and `Requirement:` clause, with no row
lacking keywords or options. `git fsck` clean.

**Two log errors, both false alarms.** vLLM logs a WARNING-level `Traceback` for an optional
Numba import (it rejects NumPy 2.5); the server is unaffected. One client `APIConnectionError`
retried and succeeded, which is why the store records zero errors.

**One real mislabel, no effect on results.** 15 of 900 calibration rollouts had
`truncated=True` with `think_status="ok"`: the model closed `</think>` and *then* hit the cap
mid-answer, so the reasoning is complete and its word count exact. Classifying on `truncated`
alone counted them as right-censored. p20 is unchanged for every source (verified by direct
recomputation) because censoring affects only the rank count, never the ordering, and
identifiability still held with the lower count. The classification is now
`truncated AND status == "unclosed"`.

**Mixed censoring levels, by construction.** gpqa and amc censored observations were recorded at
a 16384 cap and restored rather than regenerated, because only their rank matters for a low
percentile; aime's were regenerated at 32768. Harmless here — p20 sits far below the smallest
censored value in every source, which `identifiable()` checks — but it is a real detail of how
the numbers were produced and belongs in the write-up.

**Known outstanding.** The in-flight baseline imported the pre-fix scoring code, so its
CoTControl accuracy must be regenerated with `--grade-only` after it finishes. Compliance is
unaffected, since it never reads the gold answer.

**Tuning note.** vLLM reports that `--kv-cache-memory=10127396352` (9.43 GiB) would fully use
the GPU against the 8.5 GiB currently allocated, roughly 11 % more KV and so ~11 % more
throughput. Not worth restarting mid-run; worth setting for the P4 checkpoint evals.

## Truncation and censoring: the subtlest trap in this replication

If you replicate this, read this section first. Three separate mistakes here all came from the
same blind spot, and two of them produce numbers that look entirely reasonable.

### What censoring is

A rollout that hits `max_tokens` while still inside `<think>` never closes the block. You do not
learn how long its reasoning *would* have been — only that it is **at least** what you saw. In
survival-analysis terms it is right-censored: not missing data, but a lower bound. This matters
because the `number_words` limit is defined as the 20th percentile of the model's *unconstrained*
reasoning length, so the calibration is an attempt to measure a distribution whose upper tail the
token cap is quietly cutting off.

For this model the cap bites hard. At METR's 16384, 85 % of aime rollouts and 55 % of amc were
censored. METR's own models reason far more concisely, so the cap barely binds for them — which
is exactly why the trap is invisible if you assume their settings transfer.

### Mistake 1: dropping the censored rollouts (biased, and plausible-looking)

The instinct is to use only the clean observations. That is wrong here, because the discarded
rollouts are not missing at random — they are *systematically the longest*.

If a fraction `f` is censored and all censored values sit above all complete ones, the retained
set is the shortest `(1 - f)` of the distribution. The p-th percentile of what remains is
therefore roughly the `p x (1 - f)`-th percentile of the truth:

| source | censored at 16384 | p20 of survivors | true p20 | error |
|---|---:|---:|---:|---:|
| aime | 85 % | 2702 | 7451 | 2.8x too small |
| amc | 55 % | 2867 | 4249 | 1.5x |
| gpqa | 36 % | 2904 | 3478 | 1.2x |

A 2.8x-too-small word budget makes the instruction near-impossible and drives that source's
`number_words` compliance toward a spurious zero — which would have been reported as a finding
about the model rather than an artefact of our own aggregation.

**The fix is to keep them.** Because every censored rollout is longer than every complete one,
they occupy the top ranks, and a *low* percentile can be read off the complete values without
ever knowing the censored ones. Only their **count** matters, not their values.

Note this was our invention, not a deviation we inherited: METR applies no truncation check at
all (`calibrate_word_count.py` skips errors and empty reasoning, then counts words), which is
equivalent to right-censoring for a low percentile. Fixing it moved us back onto their method.

### Mistake 2: assuming a bias can always be corrected for

Raising the cap was still necessary, and this is the part that statistics alone cannot rescue.
At 16384, only 15 % of aime rollouts completed — so p20 fell *inside* the censored region. The
estimate was not merely biased, it was **unidentifiable**: no weighting scheme recovers a
percentile that lies above every value you observed. The only fix is more tokens.

This is what `identifiable()` guards. It checks both that the censored share is below
`(100 - p)` and that the estimate falls below the smallest censored observation, and reports a
lower bound rather than a number when it does not. METR has no such check, so in this regime
their code would emit a too-low number silently. At 32768 every source became identifiable,
aime included, because aime traces turn out to run ~19k tokens.

### Mistake 3: over-correcting, and throwing away good data

Having understood the bias, we then stripped **all 210** censored rollouts to regenerate them at
the higher cap. Only aime's 97 needed it. For gpqa (88 complete + 51 censored) and amc (45 + 60)
the p20 rank already fell inside the completed region, so a rollout censored at 16384 already
carried everything the percentile required — regenerating it to learn "this one is long" is pure
waste. Roughly two GPU-hours, caught after ten minutes; 106 observations were restored from a
backup instead.

The lesson generalises: censored data is not worthless data. Ask what the statistic actually
needs before discarding anything.

### The same trap in the eval, wearing different clothes

In the calibration, truncation biases a percentile. In the **evaluation** it does something
different and equally invisible: a truncated rollout is ungradeable, so it leaves the compliance
denominator entirely. Truncation is not random — it removes the long-reasoning questions, which
are the ones least likely to satisfy a reasoning constraint. So a tighter cap **inflates**
apparent compliance.

Measured on our own ReasonIF baseline, same rollouts, two caps:

| cap | gradeable | truncation | compliance |
|---|---:|---:|---:|
| 32768 | 262/300 | 14.0 % | **5.7 %** |
| 16384 | 193/300 | 35.7 % | **7.3 %** |

The tighter cap reads 1.6 pp *higher* while silently discarding 69 more rollouts. If you
replicate at 16384 without measuring your truncation rate, you will report that inflated number
and have no way to see it. It also raises a fair question about METR's published figures: if
their models truncated at all, the same inflation is present and unreported.

`eval.apply_token_cap` exists for this. Generate at the larger cap and re-project down: from
32768 rollouts you can recover the 16384 number exactly, but from 16384 rollouts you can never
recover the 32768 one, because the tokens do not exist. **The higher cap strictly dominates in
information** — run high, report both.

### Two smaller instances of the same blind spot

**A cap you forgot about looks like a bug.** The P0 smoke test capped its CoTControl probe at
2048 tokens and reported `think_status="unclosed"`, which read as a reasoning-parser failure. It
was the probe's own budget: this model spends 3-4k tokens reasoning about even a trivial MCQ.

**`truncated` is not the same as "reasoning was cut off".** 15 of 900 calibration rollouts had
`truncated=True` with `think_status="ok"` — the model closed `</think>` and *then* ran out of
tokens mid-answer. The reasoning is complete and its word count exact; only the answer is
missing. Classify on `truncated AND status == "unclosed"`, not on `truncated` alone.

### Checklist for a replicator

1. Measure your truncation rate per source and per mode **before** trusting any rate.
2. Never drop truncated rollouts from a length calibration; count them as censored.
3. Check that your percentile falls below the smallest censored value; if not, the cap is too
   low and no statistic will save you.
4. Do not regenerate censored rollouts that the statistic does not need.
5. Generate at a cap above the one you intend to report, and re-project down.
6. Distinguish "cut off inside the think block" from "cut off in the answer".

## Problems found, and what each one did

Every issue hit across P0-P2, in rough order of how much damage it would have done if it had
gone unnoticed. "Silent" means it would have produced plausible-looking wrong numbers rather
than an error.

### Silent, results-changing

**1. vLLM 0.29 renamed the reasoning field.** The qwen3 parser puts the think block on
`message.reasoning`; we read only `message.reasoning_content`. Every rollout came back
`think_status="missing"` with the reasoning text landing in `content`, which would have made
*every compliance rate zero* and looked like a real finding about the model. Caught by the P0
smoke test on the first real request. Fixed by `inference.reasoning_field()`, which reads
either name; regression-tested at the wire level against a stub server.

**2. CoTControl gold answers are text, not letters, in 2 of 3 datasets.** `hle` stores a bare
letter, but `gpqa` and `mmlu_pro_mini` store the answer *text*. `score_answer` compared the
extracted letter against `correct[:1]`, so a gold of "The compounds allow ..." became "T".
This hit 184 of our 300 drawn questions and put accuracy at 7.9 percent, below chance for
multiple choice. Caught by noticing that number was impossible, not by a test. Fixed with
`datasets.answer_letter()`, which resolves gold to an option letter at load time (all 1214
upstream rows resolve) and returns None -- unscorable -- when it cannot, rather than scoring
the row wrong. Effect on stored rollouts: accuracy 15.2 -> 58.9 percent (gpqa 78.7, mmlu_pro
84.8, hle 15.4). Compliance was never affected, as it does not read the gold answer.

**3. Dropping truncated rollouts biased the word-limit calibration.** `drop_truncated: true`
discarded the longest rollouts, so the 20th percentile of the survivors was roughly the
(20 x retained_fraction)-th percentile of the truth. aime came out at 2702 words against 7451
actual, a 2.8x error that would have made that instruction near-impossible and driven its
baseline to a spurious 0 percent. This was our own invention: METR applies no truncation
check at all, so the fix moved us back onto their method, plus an `identifiable()` guard they
lack. See the calibration section above.

**4. `.gitignore` was swallowing every deliverable.** The entry `results/` makes git skip the
directory outright, so the `!results/**/summary*.json` negations below it never fired. Every
summary and report the project had produced was untracked -- it would have looked fine until
the repo was cloned elsewhere and found empty. Now `results/**` with directory re-inclusion.
`calibration_stats.json` matched no negation either and needed its own.

**5. A 16384 token cap silently selected which questions counted.** Not a bug, but the same
class of problem: truncated rollouts are ungradeable and leave the compliance denominator, and
truncation is not random -- it removes the long-reasoning questions, which are the ones least
likely to comply. Measured on our own ReasonIF baseline: the tighter cap reads 7.3 percent
against 5.7, while discarding 69 more rollouts. Handled by raising the cap and reporting both
via `apply_token_cap`.

### Caught before they could affect anything

**6. `meta_rate` divided by the wrong denominator.** The numerator counted rollouts with usable
reasoning; the denominator was the compliance-gradeable count. Those sets differ in both
directions: an `ignore_question` rollout with no reasoning is compliance-False but not
meta-scorable, and one whose judge call failed is the reverse. Now tracks `n_meta_scored`.

**7. Errored rollouts skewed the token median.** They report 0 completion tokens and were being
included. Now excluded.

**8. Two duplicate METR reference modules with incompatible units.** Both sessions working this
repo wrote one; one took fractions and scaled internally, the other took percentages, and both
were live-imported. Consolidated into `cotctl.analysis.metr` with the unit documented.

**9. A tautological check in the smoke test.** `"," not in reasoning or True` can never fail.
Replaced with a real `grade_reasonif` call.

**10. Empty answers would have poisoned the SFT data.** 4 stage-1 rollouts had a blank answer;
training on `<think>...</think>` followed by nothing teaches the model to emit no answer at
all. Guarded in `build_sft.py`.

**11. Censoring mislabel in the calibration.** 15 of 900 rollouts had `truncated=True` with
`think_status="ok"` -- the model closed the think block and *then* hit the cap mid-answer, so
the reasoning is complete and its word count exact rather than a lower bound. Now classified as
`truncated AND unclosed`. p20 is unchanged for every source, verified by recomputation.

**12. PLAN's SFT pool count was wrong.** PLAN assumed "1000 rows, drop ~5, -> ~953". METR's
filter removes 4, and their `plan_assignments` then deduplicates, removing 59 more. The
effective pool is 937. The "drop ~5" was right; the total was not.

### Environment and tooling

**13. The README install recipe does not resolve.** `--torch-backend=cu128` cannot satisfy the
vLLM nightly's `torch==2.13.0`. PyPI's torch 2.13.0 is a CUDA 13 build, fine on this driver.
README now records what works, with transformers main installed last.

**14. FlashInfer refused sm_120 with a misleading error.** `"FlashInfer requires GPUs with sm75
or higher"` on a 5090. The arch check reports on whichever nvcc `CUDA_HOME` resolves, and
`/usr/local/cuda` here is a CUDA 12.8 toolkit (nvcc present, just off PATH) while sm_120 needs
>= 12.9. Pointing at the venv's cu13 tree fixed detection, after which FlashInfer 0.6.18's
bundled CCCL headers rejected nvcc 13.4-rc. Only the sampler wanted FlashInfer -- attention is
on FLASH_ATTN -- so `serve_vllm.sh` sets `VLLM_USE_FLASHINFER_SAMPLER=0`.

**15. `--disable-log-requests` was removed in vLLM 0.29.** Now `--no-enable-log-requests`.

**16. A dangling `ref` symlink** pointed at the previous machine's scratchpad, so the clone step
silently did nothing (the `cd` failed and short-circuited the `&&` chain).

### Process problems

**17. Two sessions shared one working tree and branch.** A commit from the other session landed
mid-edit and was later swept into a history squash; both sessions independently found and fixed
the *same* censoring bug minutes apart; and at one point both were a keystroke away from
concurrent appends to the same JSONL, where rollout lines far exceed the 4096-byte atomic-write
boundary and would have interleaved into corruption rather than merely racing. No data was
actually lost. Resolved by the user stopping the second session.

**18. Roughly two GPU-hours wasted by over-correcting.** When stripping censored rollouts for
regeneration at the higher cap, all 210 were removed when only aime's 97 needed it -- for gpqa
and amc the p20 rank already fell inside the completed data, so a rollout censored at 16384
already carried everything the percentile needed. Caught after ~10 minutes; 106 were restored.

**19. Two false alarms from bad verification code, not bad data.** A probe of the
`fast_langdetect` 80-character truncation reported "156/156 translations failing" -- it was
passing an argument the installed version does not accept, so every call raised and returned an
error sentinel. A later check reported "answer leaked into the prompt" for all 927 SFT rows --
it was matching the literal string `<answer>`, which the ReasonIF template legitimately contains
in its instruction. Both were the checker's fault. Worth recording because a verification script
that is itself wrong is more dangerous than no check.

### Known and accepted

**20. `fast_langdetect` truncates input to 80 characters by default.** Real, and it applies to
the `reasoning_language` and `english_capital` graders in the eval too. Harmless here: all 156
translated SFT traces are detected as their target language, because a translated trace opens in
that language. Recorded because a library bump could change the default.

**21. Mixed censoring levels in the calibration.** gpqa and amc censored observations sit at a
16384 cap, aime's at 32768, because the former were restored rather than regenerated. Harmless
for a rank-based low percentile -- p20 falls far below the smallest censored value in every
source -- but a real detail of how the numbers were produced.

**22. Baseline compliance of exactly zero leaves the accuracy cross-tab one-armed.** With no
compliant CoTControl rollout at baseline, whether complying costs accuracy cannot be answered
from this run. It becomes answerable after fine-tuning.

### Additional issues from the session log

**23. `pkill -f` matched the shell that invoked it.** Killing a background job by pattern killed
the very command doing the killing, three times, because the pattern string appears in that
shell's own `/proc/<pid>/cmdline`. Symptom: exit code 144 and a command that stops halfway, so
the *second* half — usually the relaunch — never runs, leaving nothing where you expected a
restarted process. Use a bracket in the pattern (`watchdog_[b]aseline`) so it cannot match its
own literal text, or resolve PIDs first and kill by number. Always re-check what is actually
running afterwards rather than assuming the command did what it said.

**24. Editing a shell script while bash is executing it.** Bash reads scripts incrementally, so
an in-place edit can make a running instance resume at a shifted byte offset and execute
garbage. Stop the process, edit, relaunch — never patch a running `.sh`.

**25. A throughput figure taken from the wrong workload.** The P0 smoke test reported ~2325
output tok/s at batch 32, which was used to project the whole project at ~12 GPU-hours. That
number came from 1024-token generations; real rollouts run to 16-32k and saturate the KV cache,
giving ~900 tok/s sustained and later ~400-600 under a 32768 cap. The honest baseline estimate
was ~14 hours, not one. Benchmark at the token budget you will actually use, and report
`Running:` vs `Waiting:` from the vLLM log — 17 of 64 requests resident is the real constraint,
not the client's concurrency setting.

**26. Long commit messages broke on shell quoting.** Parentheses and quotes inside `git commit
-m` ran as shell syntax and produced `command not found` mid-message. Write the message to a
file and use `git commit -F`.

**27. Background monitors die independently of the work they watch.** Watch processes were killed
twice while the underlying run continued perfectly. Never infer that a job has failed from its
monitor going quiet; check the process and the output file. The converse also holds — the eval
and server survived their launching session being killed, because they were started with
`setsid` and had no controlling terminal.

**28. A mid-run code change does not reach the running process.** The CoTControl accuracy fix
landed while the baseline was executing; that process had already imported the old module, so it
wrote the pre-fix accuracy at the end. Re-grading from stored rollouts (`--grade-only`) fixed it
at no GPU cost. This is the argument for storing raw rollouts and never pre-grading them.

## Standing practice

Problems go in this document as they are found, not at the end of a phase. Anything that would
have changed a reported number, or that cost real time, is written down here with what it did
and how it was caught — including mistakes in the verification code itself, since a checker that
is silently wrong is worse than no checker. A replicator should be able to read this file and
know what to look out for before spending GPU time.

## Verification status (2026-09-11)

Full re-verification of every artifact, all checks passing: SFT dataset (927 rows, unique
row_idx and question_id, all six modes, well-formed `<think>` turns, 100 percent passing their
own canonical grader, prompts stating the same constraint the grader checked, modes and
question ids matching the plan); baseline (300 ReasonIF unique, 2700 CoTControl as 300
questions x 9 modes with the identical question set in every mode, zero errors, summaries
reproducing on a fresh re-grade, accuracy reflecting the letter fix); calibration (900
rollouts, limits matching the stats file, all p20 identifiable, and the limits actually used by
the baseline run).

## CRITICAL: vLLM silently ignored the LoRA adapters (2026-09-12)

**Symptom.** The first post-fine-tuning eval showed no uplift at all: ReasonIF 5.6 % at step-30
against a 5.7 % baseline, flat on every instruction type. The later checkpoints wandered between
6.0 and 8.3 %, which looked like a weak-but-real effect.

**It was not an effect. It was sampling noise on the base model.** Served through vLLM with
`--enable-lora --lora-modules step-60=...`, the adapters produced output *byte-identical to the
base model* under greedy decoding. All four checkpoints, identical. The ~24 GPU-hours of P4
evaluation measured the base model eight times over.

**The adapter itself is fine.** Loaded directly with PEFT it works, and works well:

    prompt: "...your response should be in English and in all capital letters."
    base     caps ratio 0.14   "Thinking Process:\n\n1.  **Analyze the Request:** ..."
    step-60  caps ratio 1.00   "THE USER IS ASKING FOR THE PRODUCT OF 12 TIMES 12. ..."

All 248 `lora_B` tensors are non-zero, so training genuinely updated them, and PEFT collapsed
`target_modules` to the 12 short names vLLM expects. vLLM even JIT-compiled `_lora_expand_kernel`
at startup, so its LoRA machinery ran — it simply had no effect on the output.

**What made this dangerous.** Nothing failed. No error, no warning that mentioned the language
model (the only "will be ignored" warnings concern `visual.*` modules we deliberately excluded).
A silent no-op plus temperature 1.0 produces numbers that drift a few points between checkpoints
and look exactly like a small training effect. Had the baseline not been so precisely known, this
would have been written up as "fine-tuning produced a modest ReasonIF gain and no CoTControl
movement" — a real-sounding negative result that was entirely an artefact.

**The check that catches it, and should be run before any post-FT eval:** send one prompt at
`temperature=0` to the base and to each adapter and assert the outputs differ. Two minutes, and
it invalidates or validates the entire phase. This is now `scripts/verify_adapter.py`.

**Lesson for a replicator.** A serving stack that silently ignores an adapter is
indistinguishable from a fine-tune that did not work, and the second explanation is much more
tempting to believe. Prove the weights are live in the serving path you actually evaluate
through — not in the training framework, where they will usually work — before spending GPU time.

### Silver lining: the invalid run measures the noise floor

Because every one of those eight evaluations was really the *same base model*, they are eight
independent draws on the identical 300 ReasonIF prompts at temperature 1.0 — a direct
measurement of run-to-run sampling noise, which nothing else in this project provides. The
recovered summaries are in `results/base_replicates/` (stats in `noise_stats.json`).

    micro compliance   mean 6.63 %   sd 0.88 pp   range 5.62 - 8.37
    macro compliance   mean 6.45 %   sd 0.84 pp   range 5.42 - 8.05

**Our published 5.7 % baseline sits at the bottom of that range.** It is roughly a point low by
luck, so any uplift measured against it is flattered by about 1 pp. That belongs in the write-up.

Per instruction the spread is wildly uneven, and this is what actually governs how a result
should be read:

| instruction | min | max | mean | sd | range |
|---|---:|---:|---:|---:|---:|
| end_checker | 2.1 | 11.6 | 5.56 | 3.46 | **9.5** |
| english_capital | 0.0 | 0.0 | 0.00 | **0.00** | 0.0 |
| json_format | 0.0 | 0.0 | 0.00 | **0.00** | 0.0 |
| no_comma | 0.0 | 2.1 | 0.26 | 0.74 | 2.1 |
| number_words | 8.0 | 12.2 | 9.87 | 1.69 | 4.2 |
| reasoning_language | 21.4 | 25.0 | 23.01 | 1.25 | 3.6 |

`end_checker` swings from 2.1 % to 11.6 % on an *identical model* — a 9.5 pp range, consistent
with binomial noise at ~45 gradeable rollouts per instruction. **A per-instruction difference
below roughly 10 pp is not interpretable from a single run**, whatever its Wald interval says.
`english_capital` and `json_format`, by contrast, are hard zeros in all eight runs: the base
model never once satisfies them, so any non-zero result there is unambiguous. Those are the
cleanest places to detect a fine-tuning effect.

Overall rates are *more* stable than a binomial CI would predict (observed sd 0.88 pp against
~1.5 pp for a binomial at n≈266), because the paired design holds the question set fixed and so
removes question-selection variance. The pairing is earning its cost.

The accidental CoTControl replicate is a second full 2,700-rollout measurement landing on
exactly 0.0 % across all nine modes, confirming that floor is the model's real behaviour rather
than one unlucky draw.

**Two mistakes worth recording.** First, on discovering the runs were invalid I deleted the eight
result directories outright, reasoning that base-model rollouts mislabelled as checkpoints would
mislead whoever found them. That was hasty — the data had real value as the variance estimate
above. The summaries were recoverable from git (they had been committed thanks to the earlier
`.gitignore` fix), but the raw rollout JSONLs were gitignored and are gone for good, so none of
this can be re-graded. Mislabelled data should be relabelled, not destroyed.

Second, my first pass at this analysis scraped the numbers out of a scratch log with a regex
that silently failed to match `end_checker` rows, and I published a table omitting it — the one
instruction with by far the largest spread. The conclusion drawn from that table was too
optimistic about how stable per-instruction rates are. Recomputing from the complete recovered
summaries fixed it. A parser that silently drops rows is the same class of bug as a checker that
is itself wrong.

## Editor-model / prompt-vintage mismatch (flagged 2026-09-12)

**What we reused from METR, precisely.** No METR code runs in this pipeline — `ref/` is on the
test path only, as parity fixtures, and nothing under `src/` or `scripts/` imports
`controllability`. What we copied is *text and recipe*: the `<edited>` tag protocol, the
translate system prompt and the condense prompt (2,174 characters total, verified byte-for-byte
against the pinned commit), the transform semantics, and the `plan_assignments` logic. The judge
prompts are likewise verbatim, but from the **CoTControl** repo rather than METR. Everything
executable is ours.

**The inconsistency.** Our pinned METR clone is `9d2c4ec` (2026-05-05), five weeks *after* the
2026-04-01 blog, and at that commit `transforms.py:54` reads `editor_model = "openai/gpt-5.4"`.
We ran **gpt-4.1**, because that is what the blog states and the blog's numbers are what we
compare against. So the editor prompts come from the gpt-5.4-era code while the editor is the
blog-era model — the pairing is inconsistent whichever way it is resolved, since the blog-era
prompts are not in our clone.

**Blast radius.** Only the two LLM transforms: `number_words` (~152 condensations) and
`reasoning_language` (114 translations). The other four modes are pure string edits.

**What bounds the risk.** Every edited row is verified against the canonical ReasonIF grader
before entering the dataset, and zero rows were dropped for failing it — all 10 drops were
Stage-1 issues, for a 927/937 yield. `number_words` also falls back to hard truncation, so a
weak condensation degrades to a mechanical cut rather than a malformed row. What none of that
catches is *quality*: a condensation that sits inside the budget but reads worse than gpt-5.4
would have produced. The graders check compliance, not fidelity to the original reasoning.

**Resolved by unshallowing the clone.** The change landed in `5bd3d02` (2026-05-04), titled
*"Align SFT prompts with eval; bump editor to gpt-5.4"* — the prompts and the editor moved in
the **same commit**. The blog-era commit is `62c786d` (2026-04-01), and there `transforms.py`
hardcodes `model="openai/gpt-4.1"` with far simpler prompts and **no `<edited>` tag protocol**:

    _TRANSLATE_SYSTEM = (
        "Translate the following reasoning trace into {language}. "
        "Preserve all mathematical notation, code, and technical terms. "
        "Output ONLY the translated text."
    )

against the post-blog version we copied, which adds style/structure preservation, explicit
fragment guidance, instructions to translate quoted English, and the tag protocol.

So our position is precise: **blog-era editor model, post-blog editor prompts.** The two
self-consistent alternatives are (a) `62c786d` prompts with gpt-4.1, matching the blog whose
numbers we compare against, or (b) `9d2c4ec` prompts with gpt-5.4, matching METR's later code.
Option (a) additionally requires a code change, because the blog-era prompts return bare text
and our transforms require `<edited>` tags.

Which is *better* data is a separate question from which is more faithful: the post-blog prompts
are richer and were written to align SFT with eval, so the hybrid may well produce better
training rows than the blog-era recipe. It is simply not the blog-era recipe. Rebuilding Stage 2
under option (a) would cost ~266 editor calls and a retrain (about 45 minutes total, plus a
re-eval).

## Before porting to another model: assert the reasoning survives the template

Verified on `deepseek-ai/DeepSeek-R1-Distill-Llama-8B`, a natural candidate for a second model:

    input  : <think>\nMY REASONING HERE\n</think>\n\nTHE ANSWER
    render : <｜begin▁of▁sentence｜><｜User｜>Q<｜Assistant｜>\n\nTHE ANSWER<｜end▁of▁sentence｜>

**Its chat template silently deletes the think block from an assistant turn.** The answer
survives; the reasoning does not. Meanwhile its *generation* prompt does prefill `<think>\n`, so
inference looks entirely correct while training would see answers only.

Nothing would fail. Loss falls, `supervised_fraction` stays sane, every `lora_B` tensor ends up
non-zero, the adapter saves. It surfaces only at evaluation, as "fine-tuning did nothing" —
which is the *same* signature as the vLLM-ignoring-LoRA bug, and as a fine-tune that genuinely
did not work. Three times in this project a silent no-op nearly passed as a result.

Two changes a DeepSeek port would need: build the assistant turn manually rather than through
`apply_chat_template`, and make `ASSISTANT_HEADER` model-specific (`<｜Assistant｜>` rather than
`<|im_start|>assistant\n`). The second fails loudly — `render()` already raises when the header
is missing. The first would not, which is why `tests/test_train_data.py` now round-trips a
sentinel through the real tokenizer and asserts the reasoning is both present and supervised.

**The general rule, earned the expensive way: before spending GPU time on a new model, assert
that the thing you are training on actually survives the pipeline.** One round-trip test, two
minutes, against a class of bug that costs a day and looks like a finding.

### Additional issues from the meta-discussion judge run (2026-09-17)

**29. One `asyncio.run()` per dataset, one shared Semaphore.** `LLMJudge.__init__` creates an
`asyncio.Semaphore`, which binds to the first event loop that uses it. `judge_meta.py` called
`asyncio.run()` once per (checkpoint, suite), so every set after the first got a fresh loop and
failed instantly with `Semaphore is bound to a different event loop` — 5,596 of 8,258 rollouts,
zero HTTP calls made. The first set completed cleanly, which is what made it look like a quota
problem. Create asyncio primitives inside the coroutine that will use them, and run all work under
a single `asyncio.run()`.

**30. `pkill -f` self-match via a *log filename*.** Problem #23 again, from a new angle: the kill
command mentioned `judge_meta2.log` elsewhere on the same line, and the pattern `judge_[m]eta`
matches the substring `judge_meta` inside that filename. It killed the target, the watcher, and
the shell issuing it. Any literal in the same command that contains the pattern is a vector — not
just the script name. Match on a PID list computed by a command that mentions nothing else, or
use `ps aux | grep "[s]cripts/…"` with the bracket on the first character.

**31. A `&&` gate that checked for output, not for success.** The multi-set smoke test before the
relaunch was gated on the summary lines *printing*, not on `errors=0`. It printed `n=0 errors=3`
and the full run launched anyway — into 6,475 consecutive 429s. A gate must assert the property
you care about; "it ran" is not that property.

**32. Two API keys exhausted in one afternoon.** OpenRouter balance was ≈ $0 before the run; the
replacement OpenAI project key had roughly $1–2 of credit and ran dry after ~2,600 calls
(`429 — You have no credits remaining`). Check the balance *before* a batch job, and treat a
sudden transition from all-200 to all-429 as billing, not code.

**33. A report renderer that was not idempotent.** `render_meta_report.py` located its target
section by the `PENDING` heading, which its own first (partial) render replaced. The second render
crashed on `substring not found`. Anything that rewrites a document must find the region it
previously wrote, not the placeholder it replaced.

**34. Comparing two detectors that were not shown the same input (2026-09-18).** The CoTControl
paper's meta-discussion judge prompt truncates the trace to its first 10,000 characters; the METR
regex reads the whole trace. 97 % of base CoTControl traces exceed the cap. The first version of
`META_DISCUSSION.md` attributed the regex−judge gap (+19.5 → +38.7 pp) entirely to regex false
positives and titled a figure "the regex is almost always the one that's wrong". Re-running the
regex on the judge's own window cut the gap to +5.1 → +14.3 pp; 62 % of regex-yes/judge-no rows
had every match beyond the cap. Worse, the cap is *not* neutral across checkpoints: fine-tuning
moves narration later in the trace (median first hit 447 → 6,635 chars; first hit beyond the cap
15 % → 38 %), so the judge's headline −50.3 pp is biased upward relative to the full-trace −31.1.
Found only because the user asked for five side-by-side regex-yes/judge-no examples and the third
one narrated the instruction four times, all past char 11,919. **Practice:** before attributing a
disagreement between two measures to one of them, confirm both saw the same input; when a
reference prompt truncates, report what fraction of the data the truncation removes, per condition,
before using it for a between-condition comparison. Corrected in `META_DISCUSSION.md`,
`RESULTS.md` §5c and the figures; an uncapped re-judge (≈ 3.5× tokens) was costed and not run.

**35. `pgrep -f` self-match, third occurrence (2026-09-18).** Pausing the LLM strip run with
`for p in $(pgrep -f 'strip_llm.py'); do kill $p; done` killed the Python process *and* the shell
running the loop *and* the log watcher, because both shells' command lines contained the pattern
(exit 144). Same failure class as #23 and #30. **Practice, now mechanical:** anchor process
patterns to the start of the command line (`pgrep -f '^python scripts/strip_llm.py'`), or record
the PID at launch (`$!`) and kill that. Never match a bare filename. No data lost: every judge call
is cached (243 calls, 241/2,594 base rollouts) and the run resumes from the cache.

### Issues from the full-trace LLM labelling run (2026-09-21/22)

**36. Cost estimate missed by 2× because reasoning tokens are invisible.** The ignore_question count
prompt made gpt-5-mini reason for minutes per call at the default effort; those tokens are billed as
output but never appear in the response, so per-call cost was estimated from visible text. 612 such
calls (≈ $8) were discarded and redone at `reasoning_effort="low"` (34 s, ~4× cheaper, same counts
within noise). **Practice:** for reasoning models, read `usage.completion_tokens` (includes
reasoning) on the smoke test and set `reasoning_effort` explicitly before a large run.

**37. Provider account deactivated mid-run.** OpenAI returned 401 `account_deactivated` after
~4,000 calls; 2,116 step-60 calls failed instantly. Everything completed was cached and the run
resumed on OpenRouter with `--cache-model gpt-5-mini` so the cache keys did not change with the model
id. OpenRouter then refused calls at $0.85 remaining because it reserves the worst-case cost per
request. Final coverage is a budget-limited step-60 subset (60/mode CoTControl, ~100 of 270
ReasonIF), stated in the report banner. **Practice:** cache under a provider-independent key from
the start; check the balance *and* the per-request reservation before assuming a budget suffices.

**38. Judge output does not match the trace verbatim.** The lister escapes quotation marks (`\"`),
merges two quoted lines into one, and paraphrases ~14 % of the sentences it "quotes verbatim". The
run-time matcher therefore deleted only 75 % of listed sentences; quote/markdown normalisation in the
report raised this to 79 %, the rest is paraphrase. Strip results are correspondingly conservative;
sentence-level regex precision/recall against these labels are lower bounds. **Practice:** measure
the quote-to-text match rate before using an LLM's "verbatim" output as a deletion mask.

**39. Re-running the pipeline overwrote a finished output with a partial one.** The per-suite
output file is rewritten on every run; relaunching with `--skip-iq` to save credit rewrote the
*base* file without its (already cached) ignore_question counts, silently. Restored by one more
cached replay. **Practice:** never let a budget flag applied to one label change what is written for
another; write outputs per (label, suite, stage) or refuse to overwrite a file with fewer fields.

**36. Final checkpoint silently not saved (2026-09-23, multi-constraint arms).** `train_lora.py` planned
`ceil(n_examples / 4)` optimizer steps and saved `step-final` only when that exact step was reached. The loop
drops incomplete accumulation groups, so three of four arms finished one step short (227 vs 228, 226 vs 227,
227 vs 228) and ended with `step-210` as their last adapter; the fourth arm happened to land exactly on the
planned count. Caught only because the post-training loss check looked for `step-final/train_metrics.json`.
Fixed by saving `step-final` unconditionally at loop end; the three arms were retrained (15 min each).
**Practice:** after any training run, assert the expected final artefact exists before starting downstream
work; never derive "done" from a planned count when the loop can terminate on a different count.

**37. Process-pattern self-match, fourth and fifth time (2026-09-23).** Two more stop commands died with
exit 144 because `pkill -f`/`pgrep -f` patterns (`run_multi_eval.py`, `vllm serve`) matched the shell issuing
them. The by-PID rule from #35 was followed for the chain but not for the server lookup. **Mechanical fix
adopted for every future pattern:** write the first character of the pattern in a bracket class,
`pgrep -f '[b]in/vllm serve'`, so the regex matches the target's command line but never the literal text of
the command that contains it. Also: the multi-constraint evaluation was found to run at 4 rollouts/min
(KV-cache-bound: 13 requests running, 50 waiting, mean completion 11,900 tokens); restarted with fp8 KV cache
and halved condition sizes (1,790 requests per checkpoint instead of 3,520). Estimate before restart:
16 h/checkpoint; target after: ≤ 6 h.


**38. "No transfer" declared from the binary metric alone (2026-09-25).** The first read of the
multi-constraint results said no arm transfers to CoTControl (binary ≤ 2.5 %). The continuous scores, checked
only when the user asked about steering, show the triples arm at 0.88 uppercase, 0.66 end-of-sentence, 0.43
multiple-word suppression vs base 0.13 / 0.05 / 0.12. The binary uppercase grader fails a trace for any
lowercase letter, and 72 % of the residual lowercase in T3's traces is LaTeX; 47 % of its traces are under 1 %
lowercase. **Practice:** never state a transfer result from the all-or-nothing metric without the continuous
one beside it, and report what the residual violations *are* before calling a result null — the same lesson
as #4 (continuous scoring) and the strip test, relearned.
