# Running the programmatic rules on a new model

Read this before building a controllability training set for a model that has not been checked. The build refuses to
run until the checks below have passed for that model.

## Why a check is needed

The rules are the same for every model, but they are applied to the model's own reasoning traces, and each model lays
its reasoning out differently. A transform or grader that works on one layout can fail on another. Found so far:

| What broke | Model | Cause |
|---|---|---|
| Both word-separator rules failed on every trace | Gemma | Indented bullets with several spaces after the bullet |
| Language rules passed on 77 to 90% of traces | Gemma | The model quotes the question in English; the translator leaves quotes alone |
| Lowercase and uppercase rules failed on some traces | Qwen-7B | A few traces were partly in Japanese |
| 14 of 900 rows had no usable trace | Qwen-7B | Unclosed or empty traces |
| A name was mistranslated | Qwen-7B | The translator cut the sentence after the initials "J.K." |

All of these are fixed, but a new model can bring a new layout (tables, nested lists, headings, another language).

## What to run

1. Generate the model's own traces on the standard questions (the existing stage-1 step), giving
   `results/<model>/sft/stage1_rollouts.jsonl`.
2. Run the full check. It takes about half an hour; the translations need a GPU that nobody else is using, or about
   two hours on CPU.

   ```bash
   MT_DEVICE=cuda python scripts/check_programmatic_pool.py preflight \
       --rollouts results/<model>/sft/stage1_rollouts.jsonl --out-dir results/<model>/prog_pool \
       --mt-cache results/<model>/prog_pool/mt_cache.json --translate --procs 14 --version <model>-<date>
   ```

   It tests every rule alone and every pair on 30 of the model's traces, every bundle of 5, 6 and 7 rules with all
   rules applied together on 20 more, writes the draw of 900 rows, and then verifies the draw.
3. Read `results/<model>/prog_pool/PREFLIGHT.md`. It says PASS or FAIL and lists what to look at.
4. Build:

   ```bash
   python scripts/build_sft_programmatic.py --draw results/<model>/prog_pool/draw.json \
       --rollouts results/<model>/sft/stage1_rollouts.jsonl --out-dir results/<model>/build_prog \
       --data-prefix <prefix> --control --tokenizer <hf model id> --inspect-md results/<model>/build_prog/READ_ME_ROWS.md
   ```

   The remark step runs between the check and this build (`scripts/sft_remarks.py`; see
   `results/rl_local/META_DISCUSSION_REPORT.md`, section 8) and its `build.json` is passed with `--remarks-build`.
   With `--tokenizer`, rows longer than the trainer's limit of 4,096 tokens are left out of both the treated and the
   control file, so the two arms keep the same questions.
5. Read the rows in `READ_ME_ROWS.md` (24 by default). The automatic checks have missed things on every model so far;
   a person reading a few rows found them.

## Training

```bash
scripts/stage_programmatic.sh <model key>                         # trains the treated arm Bp and the control arm Bpctrl
STEPS="train eval checks" scripts/stage_programmatic.sh <model key>
```

- It needs the two training files in `data/sft/` (they are not in git) and waits until the GPU is free.
- A new model is added to the `case` statement at the top of the script.
- The older launchers (`results/r1qwen7/stage.sh`, `results/r1llama/stage_bnc.sh`) now hand over to this script; they
  run the previous recipe only with `OLD_RECIPE=1`.
- `checks` compares the trained model with base and with the control arm on length, hesitation words and rule talk.
  Run it before any RL or evaluation. The base model's evaluation must have been served the same way as the adapters.

## What the check decides automatically

The check fails, and the build then refuses to run, when:

- a training rule passes alone on fewer than 90% of the model's test traces;
- a language's translations pass the language grader on fewer than 90% of test traces, or are missing;
- there are fewer than 1,000 valid bundles of 6 or of 7 rules, or fewer than 30 training rules appear in any bundle;
- more than 2% of the draw's untranslated rows fail a grader on their own trace;
- more than 5% of the model's traces are unusable, or a draw row has no usable trace;
- the draw contains a rule that is not a training rule.

The thresholds are at the top of the `verify` code in `scripts/check_programmatic_pool.py`.

## The stamp

`verify` (and `preflight`, which ends with it) writes `check.json` next to the draw. It records the hash of the draw,
of the traces file and of the rule code (`programmatic.py`, `programmatic_exclusions.json`, `pool.py`,
`translate.py`). `build_sft_programmatic.py` stops if the stamp is missing, did not pass, or does not match. So:

- a draw made for one model cannot be built from another model's traces;
- after any change to the rule code, run `verify` again (about a minute without translation);
- `--skip-pool-check` overrides this and is for debugging only.

## When a rule fails on the new model

1. In `PREFLIGHT.md`, find the rule under "fail alone".
2. Apply that one rule to a failing trace and look at the output:

   ```python
   from cotctl.sft import programmatic as G
   t, args = G.apply(["<rule>"], row); print(t); print(G.grade_one("<rule>", t, args, G.question(row)))
   ```

3. Either fix the transform or grader in `src/cotctl/sft/programmatic.py`, or move the rule to `HELD` for all models.
   Do not special-case one model: the three checked models must still pass, so rerun `verify` for each of them.
4. Run `preflight` again for the new model.

A fix that changes an instruction text changes the prompts. The base-model measurement of the remark step must then be
repeated for every model, because it samples the base model on the exact training prompt.

## What the check does not cover

- **Translation quality.** The language grader only checks that the text is in the right language. Mistranslated
  words, statements turned into commands and inconsistent grammatical gender are not detected.
- **Whether inserted words read well.** They are placed by position, not by meaning.
- **Graders on model output.** The graders are tested on text written by the transforms. Before trusting evaluation
  numbers for a new model, check the graders on a sample of its real outputs.
- **The remark step.** It has its own measurement and checks; see `results/rl_local/META_DISCUSSION_REMARKS_DECISIONS.md`.

## Files

- `src/cotctl/sft/programmatic.py`: rules, exclusions, graders, `apply`, `grade_one`, `instruction`, the stamp.
- `src/cotctl/sft/translate.py`: local translation with protection of quoted material and formulas.
- `scripts/check_programmatic_pool.py`: `preflight`, or its steps `pairs`, `bundles`, `draw`, `verify`.
- `scripts/build_sft_programmatic.py`: the training-file build.
- `results/rl_local/PROGRAMMATIC_RULES_V2.md`, `PROGRAMMATIC_RULES_DECISIONS.md`: what the rules are and why.
