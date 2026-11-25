"""GRPO with the sampler on a second machine (two 16 GB cards instead of one shared card).

The trainer keeps TRL's GRPO loop and Unsloth's 4-bit model, but loads no vLLM. Each generation it posts the live LoRA
tensors and the prompts to `sampler.py` on the other machine, which runs the same Unsloth vLLM engine the one-card
setup runs (same 4-bit base, same `load_lora(load_tensors=True)` hand-off, same SamplingParams) and returns the token
ids and the sampled tokens' log-probs. Wire format: 8-byte big-endian JSON length, JSON, then safetensors bytes.
"""
import json
import struct
import urllib.request


def pack(meta: dict, blob: bytes = b"") -> bytes:
    head = json.dumps(meta).encode()
    return struct.pack(">Q", len(head)) + head + blob


def unpack(body: bytes) -> tuple[dict, bytes]:
    n = struct.unpack(">Q", body[:8])[0]
    return json.loads(body[8:8 + n]), body[8 + n:]


def lora_tensors(model) -> dict:
    return {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items() if ".lora_A." in k or ".lora_B." in k}


def lora_shape(model) -> dict:
    """What must match between the trainer's LoRA and the sampler's: rank, alpha, and every tensor's name and shape."""
    cfg = model.peft_config["default"]
    return {"r": cfg.r, "lora_alpha": cfg.lora_alpha,
            "tensors": {k: list(v.shape) for k, v in sorted(lora_tensors(model).items())}}


class RemoteSampler:
    """Stands in for TRL's VLLMGeneration on the trainer: `sync_weights` and `generate`, nothing else."""

    def __init__(self, url: str, trainer, timeout: int = 7200):
        self.url, self.trainer, self.timeout = url.rstrip("/"), trainer, timeout
        with urllib.request.urlopen(self.url + "/shape", timeout=60) as resp:
            theirs = json.loads(resp.read())
        mine = lora_shape(trainer.model)
        if theirs != mine:
            diff = [k for k in ("r", "lora_alpha") if theirs[k] != mine[k]]
            raise SystemExit(f"the sampler's LoRA differs from the trainer's ({diff or 'tensor names or shapes'})")

    def sync_weights(self) -> None:   # the LoRA travels with every generate call
        return None

    def generate(self, prompts, images, num_generations, profiler=None):
        from safetensors.torch import save
        if images is not None:
            raise SystemExit("the remote sampler is text-only")
        t = self.trainer
        # the arguments TRL's colocate mode gives vLLM: one completion per (already repeated) prompt
        sampling = {"n": 1, "repetition_penalty": t.repetition_penalty, "temperature": t.temperature, "top_p": t.top_p,
                    "top_k": t.top_k, "min_p": 0.0 if t.min_p is None else t.min_p,
                    "max_tokens": t.max_completion_length, "logprobs": 0}
        sampling.update(t.args.generation_kwargs or {})
        body = pack({"prompts": prompts, "sampling": sampling, "step": int(t.state.global_step)},
                    save(lora_tensors(t.model)))
        req = urllib.request.Request(self.url + "/generate", data=body, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            out = json.loads(resp.read())
        if "error" in out:
            raise SystemExit(f"sampler error: {out['error']}")
        if len(out["completion_ids"]) != len(prompts):
            raise SystemExit(f"the sampler returned {len(out['completion_ids'])} completions for {len(prompts)} prompts")
        return prompts, out["completion_ids"], out["logprobs"], out["logprob_token_ids"]


def attach(trainer, url: str) -> None:
    """Point a GRPOTrainer built with use_vllm=False at the remote sampler. Everything TRL does at run time for
    use_vllm=True (the sampler's log-probs for the importance-sampling correction) then applies unchanged."""
    trainer.vllm_generation = RemoteSampler(url, trainer)
    trainer.use_vllm, trainer.vllm_mode = True, "server"
    if not hasattr(trainer, "_last_loaded_step"):
        trainer._last_loaded_step = -1
