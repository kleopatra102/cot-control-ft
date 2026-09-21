"""Piece 3: residual-stream activations at chosen layers, pooled per span or per text.

Handles both checkpoint formats: the base Qwen3.5 snapshot is a multimodal wrapper
(`Qwen3_5ForConditionalGeneration`, language model under `.model.language_model` or similar); the
merged LoRA checkpoints are plain `Qwen3_5ForCausalLM`. `decoder_layers()` finds the layer list
either way. Hooks read `output[0]` of each decoder layer == the residual stream after that layer.
"""
from __future__ import annotations
from contextlib import contextmanager
import torch


def load_model(path: str, dtype=torch.bfloat16, device: str = "cuda"):
    from transformers import AutoModelForCausalLM, AutoTokenizer, AutoConfig
    tok = AutoTokenizer.from_pretrained(path)
    cfg = AutoConfig.from_pretrained(path)
    archs = cfg.architectures or []
    if any("ConditionalGeneration" in a for a in archs):
        from transformers import AutoModelForImageTextToText
        try: model = AutoModelForImageTextToText.from_pretrained(path, dtype=dtype, device_map=device)
        except Exception: model = AutoModelForCausalLM.from_pretrained(path, dtype=dtype, device_map=device)
    else:
        model = AutoModelForCausalLM.from_pretrained(path, dtype=dtype, device_map=device)
    model.eval()
    return model, tok


def decoder_layers(model) -> torch.nn.ModuleList:
    for path in ("model.layers", "model.language_model.layers", "language_model.model.layers", "language_model.layers", "layers"):
        obj = model; ok = True
        for part in path.split("."):
            if not hasattr(obj, part): ok = False; break
            obj = getattr(obj, part)
        if ok and isinstance(obj, torch.nn.ModuleList): return obj
    raise AttributeError("cannot find decoder layers")


@contextmanager
def capture(model, layers: list[int]):
    """Yields a dict layer -> hidden states [batch, seq, d] (filled after a forward pass)."""
    store: dict[int, torch.Tensor] = {}; handles = []
    mods = decoder_layers(model)
    for L in layers:
        def hook(mod, inp, out, L=L):
            store[L] = (out[0] if isinstance(out, tuple) else out).detach()
        handles.append(mods[L].register_forward_hook(hook))
    try: yield store
    finally:
        for h in handles: h.remove()


@torch.no_grad()
def span_vectors(model, tok, text: str, spans: list[tuple[int, int]], layers: list[int], device: str = "cuda") -> dict[str, torch.Tensor]:
    """One text, several token spans. Returns {'mean': [n_spans, n_layers, d], 'last': [...]} on CPU, float32."""
    ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
    with capture(model, layers) as store:
        model(input_ids=ids, use_cache=False)
    H = torch.stack([store[L][0] for L in layers], dim=1).float()   # [seq, n_layers, d]
    mean = torch.stack([H[a:b].mean(0) for a, b in spans]); last = torch.stack([H[b - 1] for a, b in spans])
    return {"mean": mean.cpu(), "last": last.cpu(), "n_tokens": ids.shape[1]}


@torch.no_grad()
def text_vector(model, tok, text: str, layers: list[int], span: tuple[int, int] | None = None, device: str = "cuda") -> torch.Tensor:
    """Mean-pooled residual over `span` (token range) or the whole text. [n_layers, d], CPU float32."""
    ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"].to(device)
    with capture(model, layers) as store:
        model(input_ids=ids, use_cache=False)
    H = torch.stack([store[L][0] for L in layers], dim=1).float()
    a, b = span if span else (0, H.shape[0])
    return H[a:b].mean(0).cpu()


def token_range(tok, text: str, char_start: int, char_len: int) -> tuple[int, int]:
    enc = tok(text, return_offsets_mapping=True, add_special_tokens=False)
    starts = [a for a, _ in enc["offset_mapping"]]
    import bisect
    a = max(bisect.bisect_right(starts, char_start) - 1, 0); b = bisect.bisect_left(starts, char_start + char_len)
    return a, max(b, a + 1)
