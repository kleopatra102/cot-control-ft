# Multi-constraint SFT on gpt-oss-20b: does it generalise to unseen constraints?

*Third model for the multi-constraint experiment (Qwen3.5-9B: `MULTI_CONSTRAINT_FINDINGS.md`; Qwen3-8B:
`QWEN3_8B_FINDINGS.md`, `TRANSFER_RECONCILIATION.md`). Decisions agreed 2026-09-29.*

## Decisions

| item | choice | why |
|---|---|---|
| training stack | Unsloth, 4-bit base, **attention-only LoRA** (q/k/v/o), r 32, α 32, lr 1e-4, bs 1 × ga 4, one epoch, max_len 8192 | transformers cannot train through the MXFP4 experts and bf16 (~41 GB) does not fit the 5090; vLLM's gpt-oss LoRA mapping covers attention only, so the adapter serves directly on the MXFP4 base |
| reasoning effort | medium, in training (system prompt "Reasoning: medium") and evaluation (`reasoning_effort`) | short traces; one setting throughout |
| answer tags | dropped: `COTCTL_NO_ANSWER_TAG=1` removes the ReasonIF "place only your final answer inside `<answer>`" line from every ReasonIF-template prompt (training, stage-1 traces, calibration, evaluation) | removes one template confound; the final channel carries the answer |
| sampling | temperature 1, top_p 1, no top_k (OpenAI's recommendation), max_tokens 32768 | `configs/gptoss.yaml` |
| serving | vLLM 0.29, Triton attention backend, MXFP4 MoE (Marlin), bf16 KV; 455k cached tokens, 11× at 40k | FlashInfer JIT fails on this host (METHODOLOGY #39) |
| format | harmony: reasoning in the analysis channel, answer in the final channel (`scripts/train_lora_gptoss.py` converts the repo's `<think>` rows) | |

## Arms (≈ 920 examples each, same 937 source questions)

| arm | constraints per example | data |
|---|---|---|
| S1 | 1 | edited gpt-oss traces |
| T3 | 3 | edited gpt-oss traces |
| Q5 | 5 | edited gpt-oss traces |
| R | 0 (matched-reasoning control) | the same unedited gpt-oss traces under the plain prompt |

Constraint set, pairing rules, hold-outs (seed 7) and editor (gpt-4.1-mini, T = 0) as in `CONSTRAINT_MIX.md`.

## Evaluation

Checkpoints: base, S1-final, T3-60, T3-final, Q5-final, R-final. Suites per checkpoint:

- ReasonIF k = 1 (6 × 20), k = 3 (16 × 10), k = 5 (2 × 20)
- CoTControl single-mode prompts, 10 × 40, plus 30 unconstrained
- never-seen IFBench-derived rules, both batches (30 rules × 20 × 2 templates)

About 1,950 requests per checkpoint. Readouts as in `TRANSFER_RECONCILIATION.md`: CoTControl split into restating
modes and novel modes, never-seen rules in the better template per rule, binary and continuous.

## Predictions

1. In-domain, T3 and Q5 beat S1; R is at base.
2. On the novel conditions the Qwen3-8B pattern repeats: a minority of whole-trace register rules move for the
   multi arms and nothing else; S1 and R stay at base.
3. gpt-oss's short medium-effort traces make all-or-nothing formats easier than on Qwen, so binary rates on the
   restating modes are higher than Qwen3-8B's.
