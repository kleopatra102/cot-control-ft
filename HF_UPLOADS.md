# Uploading models to Hugging Face

All adapters go to the private repo
[`Cot-control-spar/cot-control-treated-models`](https://huggingface.co/Cot-control-spar/cot-control-treated-models).

## Rule: every upload comes with its results

An upload is not finished until its model folder has a `README.md` with a results summary and figures. Use
[`MODEL_CARD_TEMPLATE.md`](https://huggingface.co/Cot-control-spar/cot-control-treated-models/blob/main/MODEL_CARD_TEMPLATE.md)
from the Hugging Face repo. The page must give, for treated against its control (and base where measured):

| Section | What to report |
|---|---|
| **In-domain** | Compliance on the rules seen in training: control, treated, gain with its 95% interval, number of rules up and down by 10+ points |
| **Generalisation** | The same on held-out rules, never seen in training |
| **Concentration** | How much of the gain comes from a few rules: share of the summed per-rule gain from the top 3–4 rules, and which rules they are |
| **Accuracy** | Answer accuracy without rules and with rules, with a paired test |
| **Confounds** | Reasoning length and hesitation, treated against control |
| **Setup** | Base model, training data, training settings, evaluation sampling, number of prompts per rule |
| **Caveats** | Number of runs, uncertainty per rule, anything unusual |

Figures go in `<model folder>/figures/`. For evaluations made with `scripts/run_programmatic_eval.py`, make them with:

```bash
python results/rl_local/prog_eval_g_figs/model_card_figs.py --eval-dir results/<model>/prog_eval_g \
    --out <upload folder>/<model>/figures            # --base/--control/--treated if the arm folders differ
```

It writes `compliance.png` (in-domain and generalisation), `concentration.png`, `per_rule_trained.png`,
`per_rule_held_out.png` and `accuracy.png`. Other evaluations need equivalent figures.

Example: [`non-confounded-models/R1-Distill-Qwen-7B/README.md`](https://huggingface.co/Cot-control-spar/cot-control-treated-models/blob/main/non-confounded-models/R1-Distill-Qwen-7B/README.md).

## Where things go

| Folder | What |
|---|---|
| `non-confounded-models/<model>/{base,control,treated}` | Adapters with a matched control (same questions, traces, rows and settings). `base/` only points to the base model. |
| `confounded-models/` | Earlier adapters without an identical-data control |
| `post-rl/` | RL adapters |

- Keep the repo private.
- Never overwrite or move another person's folder without asking them.
- Add a line for the new model to the table on the repo's front page (`README.md`).
- Upload adapters only (PEFT format), never a copy of the base model.
