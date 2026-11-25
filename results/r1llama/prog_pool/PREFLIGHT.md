# Pool check for results/r1llama/sft/stage1_rollouts.jsonl

Result: **PASS**

- traces: 937; unusable (unclosed or empty) 0.1%
- training rules that fail alone on some of 30 test traces: none
- draw rows: 900; without a usable trace 0; untranslated rows built and graded 684; failing 0 
- valid bundles of 6: 15,042, using 39 rules
- valid bundles of 7: 12,347, using 39 rules

## What to do

- PASS: build with scripts/build_sft_programmatic.py, then read about 20 built rows (its --inspect-md option writes them to a file).
- A rule fails alone: look at one failing trace; the model's layout (bullets, tables, another language) usually breaks an assumption of the transform. Fix it in src/cotctl/sft/programmatic.py or move the rule to HELD, then run preflight again.
- Few bundles or many failing rows: run preflight again after the fix; never build from a draw that was checked on another model's traces.
