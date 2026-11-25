"""Apply the split-sampler switch to a copy of ilinca-strict's rs/hf_rl/train.py: RL_REMOTE_SAMPLER=<url> loads no
vLLM on the trainer and points GRPO at sampler.py on another machine. Unset, the file behaves as before."""
import sys
p = sys.argv[1]; s = open(p).read()
if "RL_REMOTE_SAMPLER" in s:
    sys.exit("already patched")
def sub(old, new):
    global s
    if s.count(old) != 1: sys.exit(f"anchor not found once: {old[:60]}")
    s = s.replace(old, new)
if "\nimport os\n" not in s:
    sub("\nimport inspect\n", "\nimport inspect\nimport os\n")
sub("load_in_4bit=True, fast_inference=True,", "load_in_4bit=True, fast_inference=not os.environ.get(\"RL_REMOTE_SAMPLER\"),")
sub("    ensure_vllm_lora(model)\n    n_train", "    if not os.environ.get(\"RL_REMOTE_SAMPLER\") or os.environ.get(\"RL_IS_SAMPLER\"):\n        ensure_vllm_lora(model)\n    n_train")
sub("bf16=True, use_vllm=True,", "bf16=True, use_vllm=not os.environ.get(\"RL_REMOTE_SAMPLER\"),")
sub("    trainer.train()\n    return trainer.state.log_history\n\n\ndef versions",
    "    if os.environ.get(\"RL_REMOTE_SAMPLER\"):\n        from rs.hf_rl import split\n        split.attach(trainer, os.environ[\"RL_REMOTE_SAMPLER\"])\n    trainer.train()\n    return trainer.state.log_history\n\n\ndef versions")
open(p, "w").write(s)
print("patched")
