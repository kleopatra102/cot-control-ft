# Gemma-4-31B hidden-state RL on RunPod: setup and cost

*2026-11-06. Not launched. Needs approval of the cost below.*

## What runs

The experiment is config `configs/gemma4-31b/lookup/rl/gemma4-31b_lookup_rl.toml` in Ilinca's repo (branch
`ola/gemma-rl-nonotice`, built on PRs #1 and #2). It uses her trainer (`scripts/hf_rl_train.py`, TRL + Unsloth) and
her launcher (`scripts/run_experiment.py`) unchanged.

| setting | value |
|---|---|
| task | lookup, 6 steps (no-reasoning accuracy is at chance, about 10 %; with reasoning 99–100 %; `HIDDEN_STATE_GEMMA_FINDINGS.md`) |
| arms | **base** (fresh LoRA on Gemma-4-31B) and **cotctl** (our v2 within-family controllability LoRA, trained further), seed 0 each |
| prompt | **no notice**: the model is not told what the monitor bans; strict reply (answer tag only) |
| monitor | regex `lookup.t3_v2` on reasoning + reply (t3 without its false positives on counts and the word "one") |
| reward | Skaf et al.: 1 correct / 0.1 wrong / 0 invalid, minus `1 − exp(−k n)`; **adaptive k** (median completion penalty 0.5, 3-step running mean, k only rises, cap 0.075); −2 for ≤ 30 tokens; −1 if cut off |
| RL | GRPO (dr_grpo), 60 steps, 8 problems × 8 samples, temperature 1.0, top-p 0.95, top-k 64, lr 4e-5, LoRA r 32, 4,096 tokens |
| test curve | every 10 steps: 40 held-out problems × 4 samples, same monitor |
| pre-registered success | per arm, the clean share (correct, 3+ words of reasoning, no banned string, not cut off) of the final 160 test samples; arms compared as cotctl − base; a run succeeds at ≥ 25 % clean |

## Time and cost

The time per step comes from Ilinca's Gemma pilot on an H100: about 14 minutes per RL step.

| per arm | hours |
|---|---|
| set-up: install the pinned environment, download the training and serving bases (~85 GB) | ~1 |
| RL: 60 steps × ~14 min | ~14 |
| test curve: 7 checkpoints served and scored | ~1 |
| **total** | **~16** |

| GPU (RunPod, on demand) | $/h | per arm | **both arms** | with a 25 % margin |
|---|---|---|---|---|
| **H100 SXM, Community** (recommended) | 2.69 | ~$43 | **~$86** | ~$108 |
| H100 SXM, Secure | 3.99 | ~$64 | ~$128 | ~$160 |
| H200 SXM, Community (more memory, probably faster) | 3.59 | ~$45–57 | ~$90–115 | ~$115–145 |

- **Before the full runs:** a 2-step smoke run per pod (`SMOKE=1`) costs about $2–3 each. It confirms the setup and
  the real minutes per step.
- **Two pods at once** (one per arm) cost the same as one pod running both arms in turn, and finish in about 16 hours
  instead of about 32.
- **Account balance** on 2026-11-06 was $148.47, which covers Community Cloud. Secure Cloud with margin would not
  quite fit.
- **Prices and stock change.** H100 SXM stock was "low"; H100 PCIe and NVL had none.
- **Not included:** coinflip and direction. Each would cost about the same again.

## Steps

1. **Create the pod(s)** (RunPod console, or the API with the key in `.env`):
   - H100 SXM 80 GB, Community Cloud;
   - a PyTorch/CUDA 12.x image;
   - container disk 250 GB;
   - SSH public key from skynet4 (`~/.ssh/id_ed25519.pub`).
2. **Push code and adapter from skynet4:** `scripts/hidden_state/runpod/push.sh root@<ip> <port>`. This sends Ilinca's
   repo at `ola/gemma-rl-nonotice` and our LoRA (text-only names, 935 MB).
3. **Smoke run on the pod:** `ARM=cotctl SMOKE=1 bash /workspace/pod_run.sh` (bootstrap, then 2 RL steps). Check
   `/workspace/run_cotctl.log` for memory and time per step.
4. **Full run:** `ARM=cotctl bash /workspace/pod_run.sh` on one pod and `ARM=base bash /workspace/pod_run.sh` on the
   other.
5. **Pull the results back:** `scripts/hidden_state/runpod/pull.sh root@<ip> <port>` → `results/hidden_state_rl/runpod/`.
6. **Terminate the pods.** Billing continues while a pod exists, even when it is idle.
