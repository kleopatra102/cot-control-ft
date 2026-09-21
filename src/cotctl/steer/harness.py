"""Piece 5: steered generation. Adds coef * unit direction to the residual stream at one layer, at
every position, during HF generation. Writes rollouts in the same schema as `cotctl.inference.Rollout`
so every grader, continuous score and the LLM lister apply unchanged.
Sampling matches the eval: temperature 1.0, top_p 0.95, top_k 20, user message only.
"""
from __future__ import annotations
import json, time
from contextlib import contextmanager
from pathlib import Path
import torch
from .activations import decoder_layers
from ..inference import split_think


@contextmanager
def steer(model, layer: int, unit: torch.Tensor, coef: float):
    mods = decoder_layers(model)
    if coef == 0.0:
        yield; return
    p = next(mods[layer].parameters()); add = (coef * unit).to(device=p.device, dtype=p.dtype)
    def hook(mod, inp, out):
        if isinstance(out, tuple): return (out[0] + add,) + tuple(out[1:])
        return out + add
    h = mods[layer].register_forward_hook(hook)
    try: yield
    finally: h.remove()


@torch.no_grad()
def generate_steered(model, tok, prompts: list[dict], layer: int, unit: torch.Tensor, coef: float, max_new_tokens: int = 8192,
                     batch_size: int = 4, temperature: float = 1.0, top_p: float = 0.95, top_k: int = 20, seed: int | None = None,
                     model_name: str = "", out_path: Path | None = None, meta_extra: dict | None = None) -> list[dict]:
    """prompts: dicts with sample_id, mode, prompt, meta. Returns rollout dicts (and appends to out_path)."""
    tok.padding_side = "left"
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    if seed is not None: torch.manual_seed(seed)
    rollouts = []
    for i in range(0, len(prompts), batch_size):
        batch = prompts[i:i + batch_size]
        texts = [tok.apply_chat_template([{"role": "user", "content": p["prompt"]}], tokenize=False, add_generation_prompt=True) for p in batch]
        enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
        t0 = time.time()
        with steer(model, layer, unit, coef):
            out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=True, temperature=temperature, top_p=top_p, top_k=top_k, pad_token_id=tok.pad_token_id)
        dt = time.time() - t0
        for j, p in enumerate(batch):
            gen = out[j, enc["input_ids"].shape[1]:]; n_new = int((gen != tok.pad_token_id).sum())
            text = tok.decode(gen, skip_special_tokens=True)
            finished = bool((gen == tok.eos_token_id).any()) or n_new < max_new_tokens
            # Qwen3.5's chat template already opens the think block in the generation prompt, so the
            # generated text starts inside it; restore the opening tag before splitting.
            if texts[j].rstrip().endswith("<think>") and "<think>" not in text:
                text = "<think>\n" + text
            reasoning, answer, status = split_think(text, None, None if finished else "length")
            r = {"sample_id": p["sample_id"], "mode": p["mode"], "prompt": p["prompt"], "reasoning": reasoning, "answer": answer, "think_status": status,
                 "finish_reason": "stop" if finished else "length", "truncated": not finished, "prompt_tokens": int(enc["attention_mask"][j].sum()),
                 "completion_tokens": n_new, "latency_s": dt / len(batch), "model": model_name, "error": None,
                 "meta": {**(p.get("meta") or {}), "steer_layer": layer, "steer_coef": coef, **(meta_extra or {})}}
            rollouts.append(r)
            if out_path:
                with open(out_path, "a", encoding="utf-8") as f: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rollouts
