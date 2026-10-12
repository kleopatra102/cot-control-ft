#!/usr/bin/env bash
# Gemma-4-31B-IT (QAT 4-bit) + the v2 within-family adapter (served as v2g-B) on skynet4, for scripts/stego/hide.py --profile gemma.
cd "$(dirname "$0")/../.."
R=results/v2_gemma; export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
KV_DTYPE=fp8 ATTN_BACKEND=TRITON_ATTN MAX_LEN=16384 GPU_UTIL=0.92 MODEL=google/gemma-4-31B-it-qat-w4a16-ct REASONING_PARSER=gemma4 \
  MAX_SEQS=32 MAX_LORAS=1 EXTRA_ARGS='--limit-mm-per-prompt {"image":0,"audio":0}' exec scripts/serve_vllm.sh v2g-B=$R/ckpts/B/step-final
