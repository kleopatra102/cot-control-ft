#!/usr/bin/env bash
# Haskins SDF documents (gpt-5-mini via OpenRouter), his gen_data.py and universes. ~1,000 docs per set.
set -uo pipefail
cd "$(dirname "$0")/../.."  # repo root
set -a; . ./.env; set +a
H=/home/ola/dev/ext/haskins/defect_concealment; PY=.venv-tinker/bin/python; O=results/haskins/docs
$PY $H/scripts/training/gen_data.py --universe $H/data/training/universe_v3_behavioral.md --facts $H/data/training/facts_v3_behavioral.json \
  --prompt_variant behavioral --num_ideas 28 --docs_per_idea 3 --openrouter --out_dir $O/behavioral_1 > $O/behavioral_1.log 2>&1 &
$PY $H/scripts/training/gen_data.py --universe $H/data/training/universe_v3_behavioral.md --facts $H/data/training/facts_v3_behavioral.json \
  --prompt_variant behavioral --num_ideas 28 --docs_per_idea 3 --openrouter --out_dir $O/behavioral_2 > $O/behavioral_2.log 2>&1 &
$PY $H/scripts/training/gen_data.py --universe $H/data/training/universe_v3_avoidance.md --facts $H/data/training/facts_v3_avoidance.json \
  --num_ideas 21 --docs_per_idea 3 --openrouter --out_dir $O/avoidance > $O/avoidance.log 2>&1 &
wait
for d in behavioral_1 behavioral_2 avoidance; do echo "$d $(cat $O/$d/*/synth_docs.jsonl 2>/dev/null | wc -l) docs"; done
