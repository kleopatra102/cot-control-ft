"""Async client for a local OpenAI-compatible vLLM server + a resumable rollout store.

One *rollout* is one sampled completion for a (sample_id, mode) pair. Rollouts are stored
raw — reasoning text, answer text, usage, finish reason — and never pre-graded, so that
re-grading (e.g. after a grader fix or a new `number_words` calibration) costs nothing.

Think-block handling follows PLAN.md: the reasoning is whatever sits inside `<think>…</think>`.
With `--reasoning-parser qwen3` vLLM splits that out onto the message: the field is
`reasoning` in vLLM 0.29 and `reasoning_content` in older builds, so we read whichever is
populated. We also parse raw `<think>` tags out of `content` as a fallback (an adapter can
emit them literally).
A rollout whose think block is missing, empty or unclosed gets `think_status != "ok"` and is
excluded from compliance rates by `eval.py` (except `ignore_question`, which counts as False).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

log = logging.getLogger(__name__)

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

# think_status values
OK = "ok"
MISSING = "missing"      # no think block at all
EMPTY = "empty"          # think block present but whitespace-only
UNCLOSED = "unclosed"    # generation hit the token cap inside the think block
GRADEABLE = (OK,)


@dataclass
class SamplingParams:
    """METR: temperature 1.0, max_tokens 16384, no system prompt.
    top_p/top_k are Qwen's recommended thinking-mode defaults; no presence_penalty
    (it would bias the meow/repeat modes)."""

    temperature: float = 1.0
    max_tokens: int = 16384
    top_p: float = 0.95
    top_k: int = 20
    seed: int | None = None
    reasoning_effort: str | None = None  # gpt-oss only: low | medium | high

    def to_request(self) -> dict:
        body: dict[str, Any] = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }
        if self.top_k is not None:
            body["extra_body"] = {"top_k": self.top_k}
        if self.seed is not None:
            body["seed"] = self.seed
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        return body


@dataclass
class Rollout:
    sample_id: str
    mode: str
    prompt: str
    reasoning: str
    answer: str
    think_status: str
    finish_reason: str | None = None
    truncated: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    model: str = ""
    error: str | None = None
    meta: dict = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_id, self.mode)


# ---------------------------------------------------------------------------
# think-block extraction
# ---------------------------------------------------------------------------


def reasoning_field(message) -> str | None:
    """Read the parser's reasoning off a response message.

    vLLM renamed this field: 0.29 emits `reasoning`, older builds `reasoning_content`.
    Accepts an object or a dict so it works with both the SDK model and raw JSON.
    """
    for name in ("reasoning_content", "reasoning"):
        value = message.get(name) if isinstance(message, dict) else getattr(message, name, None)
        if value:
            return value
    return None


def split_think(
    content: str | None,
    reasoning_content: str | None = None,
    finish_reason: str | None = None,
) -> tuple[str, str, str]:
    """Return `(reasoning, answer, think_status)`.

    `reasoning_content` is what vLLM's qwen3 reasoning parser produced (already stripped of the
    tags); `content` is the post-`</think>` answer. When the parser is off, or when an adapter
    emits literal tags inside `content`, we fall back to regex extraction.
    """
    content = content or ""
    reasoning_content = reasoning_content or ""

    if reasoning_content.strip():
        # Parser path. Only truncation can leave the block unclosed, and then vLLM has no
        # answer text to report.
        if finish_reason == "length" and not content.strip():
            return reasoning_content, "", UNCLOSED
        return reasoning_content, content, OK

    m = _THINK_RE.search(content)
    if m:
        reasoning = m.group(1)
        answer = content[m.end():]
        return reasoning, answer, OK if reasoning.strip() else EMPTY

    if THINK_OPEN in content:  # opened, never closed
        return content.split(THINK_OPEN, 1)[1], "", UNCLOSED

    if reasoning_content:  # present but whitespace-only
        return reasoning_content, content, EMPTY

    return "", content, MISSING


# ---------------------------------------------------------------------------
# resumable JSONL store
# ---------------------------------------------------------------------------


class RolloutStore:
    """Append-only JSONL keyed by `(sample_id, mode)`; re-running skips completed keys.

    Rollouts that recorded an `error` are *not* treated as complete, so a re-run retries them.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[tuple[str, str]] = set()
        self._fh = None
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        bad = 0
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1  # truncated last line from an interrupted run
                    continue
                if not r.get("error"):
                    self._done.add((r["sample_id"], r["mode"]))
        if bad:
            log.warning("%s: skipped %d unparsable line(s)", self.path, bad)

    def __contains__(self, key: tuple[str, str]) -> bool:
        return key in self._done

    def __len__(self) -> int:
        return len(self._done)

    def append(self, rollout: Rollout) -> None:
        if self._fh is None:
            self._fh = open(self.path, "a", encoding="utf-8")
        self._fh.write(json.dumps(asdict(rollout), ensure_ascii=False) + "\n")
        self._fh.flush()
        if not rollout.error:
            self._done.add(rollout.key)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "RolloutStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def read_all(self, latest_only: bool = True) -> list[dict]:
        """All records; with `latest_only`, the last successful record per key (retries win)."""
        if not self.path.exists():
            return []
        rows = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not latest_only:
            return rows
        best: dict[tuple[str, str], dict] = {}
        for r in rows:
            k = (r["sample_id"], r["mode"])
            if r.get("error") and k in best:
                continue
            best[k] = r
        return list(best.values())


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------


@dataclass
class Request:
    """One unit of work: a prompt to send, plus the metadata to carry into the rollout."""

    sample_id: str
    mode: str
    prompt: str
    meta: dict = field(default_factory=dict)
    developer: str | None = None  # optional instructions message before the user turn (gpt-oss: developer role)

    @property
    def key(self) -> tuple[str, str]:
        return (self.sample_id, self.mode)


class VLLMClient:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        concurrency: int = 32,
        max_retries: int = 4,
        timeout: float = 1800.0,
    ):
        from openai import AsyncOpenAI

        self.model = model
        self.base_url = base_url or os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
        self.concurrency = concurrency
        self.max_retries = max_retries
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=api_key or os.environ.get("VLLM_API_KEY", "EMPTY"),
            timeout=timeout,
            max_retries=0,  # we retry ourselves so failures land in the store
        )

    async def _one(self, req: Request, sampling: SamplingParams) -> Rollout:
        body = sampling.to_request()
        last_err = ""
        for attempt in range(self.max_retries):
            t0 = time.monotonic()
            try:
                resp = await self._client.chat.completions.create(
                    model=self.model,
                    messages=([{"role": "developer", "content": req.developer}] if req.developer else [])
                    + [{"role": "user", "content": req.prompt}],  # no system prompt (METR); developer only when a template asks for it
                    **body,
                )
            except Exception as e:  # noqa: BLE001 - server hiccups, timeouts, 5xx
                last_err = f"{type(e).__name__}: {e}"
                log.warning("%s/%s attempt %d failed: %s", req.sample_id, req.mode, attempt + 1, last_err)
                await asyncio.sleep(min(2**attempt, 30))
                continue

            latency = time.monotonic() - t0
            choice = resp.choices[0]
            msg = choice.message
            reasoning, answer, status = split_think(
                msg.content, reasoning_field(msg), choice.finish_reason
            )
            usage = resp.usage
            return Rollout(
                sample_id=req.sample_id,
                mode=req.mode,
                prompt=req.prompt,
                reasoning=reasoning,
                answer=answer,
                think_status=status,
                finish_reason=choice.finish_reason,
                truncated=choice.finish_reason == "length",
                prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
                latency_s=latency,
                model=self.model,
                meta=dict(req.meta),
            )

        return Rollout(
            sample_id=req.sample_id,
            mode=req.mode,
            prompt=req.prompt,
            reasoning="",
            answer="",
            think_status=MISSING,
            model=self.model,
            error=last_err or "unknown error",
            meta=dict(req.meta),
        )

    async def run(
        self,
        requests: Sequence[Request],
        sampling: SamplingParams,
        store: RolloutStore | None = None,
        progress: bool = True,
        desc: str = "rollouts",
    ) -> list[Rollout]:
        """Run `requests` with bounded concurrency, appending to `store` as each finishes.

        Requests already present in the store are skipped, which makes whole runs resumable.
        """
        todo = [r for r in requests if store is None or r.key not in store]
        skipped = len(requests) - len(todo)
        if skipped:
            log.info("%s: skipping %d already-complete rollout(s)", desc, skipped)
        if not todo:
            return []

        sem = asyncio.Semaphore(self.concurrency)
        out: list[Rollout] = []
        bar = None
        if progress:
            try:
                from tqdm.auto import tqdm

                bar = tqdm(total=len(todo), desc=desc)
            except ImportError:
                pass
        lock = asyncio.Lock()

        async def worker(req: Request) -> None:
            async with sem:
                rollout = await self._one(req, sampling)
            async with lock:  # keep JSONL lines interleaved but never interleaved *within* a line
                out.append(rollout)
                if store is not None:
                    store.append(rollout)
                if bar is not None:
                    bar.update(1)

        await asyncio.gather(*(worker(r) for r in todo))
        if bar is not None:
            bar.close()
        return out


def run_sync(
    client: VLLMClient,
    requests: Sequence[Request],
    sampling: SamplingParams,
    store: RolloutStore | None = None,
    **kwargs,
) -> list[Rollout]:
    return asyncio.run(client.run(requests, sampling, store, **kwargs))


def wait_for_server(base_url: str | None = None, timeout: float = 1800.0, interval: float = 5.0) -> str:
    """Block until the vLLM server answers `/v1/models`; returns the served model id."""
    import httpx

    base_url = (base_url or os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")).rstrip("/")
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{base_url}/models", timeout=10.0)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    return data[0]["id"]
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        time.sleep(interval)
    raise TimeoutError(f"vLLM server at {base_url} not ready after {timeout}s ({last})")
