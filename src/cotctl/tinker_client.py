"""Sampling through Tinker (Thinking Machines), with the same interface as inference.VLLMClient, so the v2 scripts can
run on models Tinker hosts without a local GPU (`scripts/v2/screen.py --backend tinker`).

The prompt is rendered with the tinker-cookbook renderer for the model (thinking on), and the response is parsed back
into reasoning (ThinkingPart) and answer (TextPart). Needs TINKER_API_KEY and the .venv-tinker environment.
"""
from __future__ import annotations
import asyncio, logging, time
from cotctl.inference import MISSING, OK, UNCLOSED, Request, Rollout, SamplingParams, VLLMClient

log = logging.getLogger(__name__)


class TinkerClient(VLLMClient):
    def __init__(self, model: str, renderer: str, concurrency: int = 64, max_retries: int = 4, model_path: str | None = None):
        import tinker
        from tinker_cookbook import renderers
        self.model, self.concurrency, self.max_retries = model, concurrency, max_retries
        svc = tinker.ServiceClient()  # model_path: a trained LoRA (tinker://...); its tokenizer and renderer are the base model's
        self._sc = svc.create_sampling_client(model_path=model_path) if model_path else svc.create_sampling_client(base_model=model)
        self._tok = self._sc.get_tokenizer()
        self._r = renderers.get_renderer(renderer, self._tok)
        self._tinker = tinker

    async def _one(self, req: Request, sampling: SamplingParams) -> Rollout:
        msgs = ([{"role": "system", "content": req.system}] if req.system else []) + \
               ([{"role": "system", "content": req.developer}] if req.developer else []) + [{"role": "user", "content": req.prompt}]
        prefill = req.meta.get("prefill")  # text placed at the start of the reasoning (inside the thinking block)
        prompt = self._r.build_generation_prompt(msgs, prefill=prefill) if prefill else self._r.build_generation_prompt(msgs)
        sp = self._tinker.SamplingParams(max_tokens=sampling.max_tokens, temperature=sampling.temperature, top_p=sampling.top_p,
                                         top_k=sampling.top_k if sampling.top_k else -1, stop=self._r.get_stop_sequences())
        last = ""
        for attempt in range(self.max_retries):
            t0 = time.monotonic()
            try:
                res = await self._sc.sample_async(prompt=prompt, num_samples=1, sampling_params=sp)
            except Exception as e:  # noqa: BLE001 - rate limits, transient server errors
                last = f"{type(e).__name__}: {e}"; log.warning("%s/%s attempt %d: %s", req.sample_id, req.mode, attempt + 1, last)
                await asyncio.sleep(min(2 ** attempt * 5, 60)); continue
            seq = res.sequences[0]; toks = list(seq.tokens)
            msg, _ = self._r.parse_response(toks)
            content = msg.get("content")
            parts = content if isinstance(content, list) else [{"type": "text", "text": content or ""}]
            reasoning = "".join(p.get("thinking", "") for p in parts if p.get("type") == "thinking").strip()
            if prefill: reasoning = (prefill + reasoning).strip()
            answer = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            truncated = str(getattr(seq, "stop_reason", "")).endswith("length") or len(toks) >= sampling.max_tokens
            status = OK if reasoning and not truncated else (UNCLOSED if reasoning else MISSING)
            return Rollout(sample_id=req.sample_id, mode=req.mode, prompt=req.prompt, reasoning=reasoning, answer=answer, think_status=status,
                           finish_reason="length" if truncated else "stop", truncated=truncated, prompt_tokens=prompt.length,
                           completion_tokens=len(toks), latency_s=time.monotonic() - t0, model=self.model, meta=dict(req.meta))
        return Rollout(sample_id=req.sample_id, mode=req.mode, prompt=req.prompt, reasoning="", answer="", think_status=MISSING,
                       model=self.model, error=last or "unknown error", meta=dict(req.meta))
