"""Per-model settings for the v2 scripts, chosen with the V2_RUN environment variable (default gptoss)."""
import os
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
RUNS = {
    "gptoss": dict(title="gpt-oss-20b", stage1="results/gptoss/sft/stage1_rollouts.jsonl", thresholds="data/v2_thresholds_gpt-oss-20b.json",
                   root="results/v2_gptoss", data_prefix="v2_gptoss", fig_prefix="v2_gptoss",
                   sampling=dict(temperature=1.0, top_p=1.0, top_k=None, reasoning_effort="medium")),
    "gemma": dict(title="Gemma-4-31B-IT (QAT 4-bit)", stage1="results/v2_gemma/sft/stage1_rollouts.jsonl", thresholds="data/v2_thresholds_gemma-4-31b.json",
                  root="results/v2_gemma", data_prefix="v2_gemma", fig_prefix="v2_gemma",
                  sampling=dict(temperature=1.0, top_p=0.95, top_k=64, chat_template_kwargs={"enable_thinking": True})),
}
NAME = os.environ.get("V2_RUN", "gptoss")
RUN = {k: (REPO / v if k in ("stage1", "thresholds", "root") else v) for k, v in RUNS[NAME].items()}
