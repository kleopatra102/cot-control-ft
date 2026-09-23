#!/usr/bin/env bash
# Serve Qwen3.5-9B for eval / SFT rollouts on the RTX 5090.
#
#   scripts/serve_vllm.sh                      # base model
#   scripts/serve_vllm.sh path/to/adapter      # base + one LoRA adapter (named "ft")
#
# --reasoning-parser qwen3 splits the <think> block into message.reasoning_content, which is
# what src/cotctl/inference.py reads. --enable-lora is always on so that base and post-FT evals
# run against an identically-configured server.
set -euo pipefail

cd "$(dirname "$0")/.."
source .venv/bin/activate

# FlashInfer JIT-compiles its sampling kernels and picks nvcc from CUDA_HOME, defaulting to
# /usr/local/cuda -- which on this host is a CUDA 12.8 toolkit. sm_120 (Blackwell) needs
# CUDA >= 12.9, so with the system toolkit FlashInfer resolves an empty target-arch set and
# dies with the misleading "FlashInfer requires GPUs with sm75 or higher". Point it at the
# CUDA 13.4 nvcc that ships inside the venv with torch cu130.
CU13="$PWD/.venv/lib/python3.12/site-packages/nvidia/cu13"
if [[ -x "$CU13/bin/nvcc" ]]; then
  export CUDA_HOME="$CU13"
else
  echo "warning: expected the cu13 toolkit at $CU13; FlashInfer may fall back to $(command -v nvcc || echo /usr/local/cuda)" >&2
fi

# ...but that nvcc is 13.4-rc, and FlashInfer 0.6.18 bundles CCCL headers that reject it
# ("CUDA compiler and CUDA toolkit headers are incompatible"), so its sampling kernels will
# not JIT-build here either way. Attention runs on FLASH_ATTN regardless; only the sampler
# would use FlashInfer, so fall back to vLLM's native top-k/top-p. Same sampling semantics,
# marginally slower. Revisit if nvidia-cuda-nvcc is ever pinned back to 13.0.x.
export VLLM_USE_FLASHINFER_SAMPLER=0

MODEL="${MODEL:-Qwen/Qwen3.5-9B}"
PORT="${PORT:-8000}"
MAX_LEN="${MAX_LEN:-40960}"
GPU_UTIL="${GPU_UTIL:-0.94}"
# Any number of adapters: scripts/serve_vllm.sh step-60=path step-final=path ...
# A bare path (no "name=") is served as "ft", preserving the old single-adapter usage.
ADAPTERS=("$@")

ARGS=(
  --model "$MODEL"
  --served-model-name "$MODEL"
  --port "$PORT"
  --max-model-len "$MAX_LEN"
  --gpu-memory-utilization "$GPU_UTIL"
  --dtype bfloat16
  --reasoning-parser qwen3
  --enable-lora
  --max-lora-rank 32
  --max-loras 1
  --no-enable-log-requests
)
if [[ -n "${KV_DTYPE:-}" ]]; then ARGS+=(--kv-cache-dtype "$KV_DTYPE"); echo "  (kv-cache-dtype=$KV_DTYPE)"; fi

if [[ ${#ADAPTERS[@]} -gt 0 ]]; then
  SPECS=()
  for a in "${ADAPTERS[@]}"; do
    if [[ "$a" == *"="* ]]; then SPECS+=("$a"); else SPECS+=("ft=$a"); fi
  done
  ARGS+=(--lora-modules "${SPECS[@]}")
  # max_loras caps how many adapters are *resident in GPU memory* at once; the rest are swapped
  # in from host memory on demand. Each r=32 adapter is ~350 MB, which comes straight out of the
  # KV cache, so keep this small when evals run one checkpoint at a time and only raise it if
  # requests genuinely interleave across adapters.
  N_RESIDENT="${MAX_LORAS:-2}"
  [[ "$N_RESIDENT" -gt "${#SPECS[@]}" ]] && N_RESIDENT="${#SPECS[@]}"
  for i in "${!ARGS[@]}"; do
    if [[ "${ARGS[$i]}" == "--max-loras" ]]; then ARGS[$((i+1))]="$N_RESIDENT"; fi
  done
  echo "  (max_loras=$N_RESIDENT resident of ${#SPECS[@]} served)"
  echo "serving $MODEL + ${#SPECS[@]} LoRA adapter(s): ${SPECS[*]}"
else
  echo "serving $MODEL (base)"
fi

exec vllm serve "${ARGS[@]}"
