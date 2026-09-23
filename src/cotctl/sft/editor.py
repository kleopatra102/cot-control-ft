"""Editor LLM for the two Stage-2 transforms that need one (translate, condense).

PLAN.md fixes the editor as `gpt-4.1` — what METR's blog states, though their later code
defaults to a newer model. Reached through OpenRouter here, like the judge.

Responses are cached on disk by a hash of (system, user, temperature, model), so re-running
Stage 2 after a crash, or re-building the dataset with a different mode assignment, does not
re-pay for edits already made.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

EDITOR_MODEL = "openai/gpt-4.1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Editor:
    def __init__(
        self,
        model: str = EDITOR_MODEL,
        cache_path: Path | str | None = None,
        concurrency: int = 8,
        max_retries: int = 4,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 16384,
    ):
        from openai import AsyncOpenAI

        key = api_key or os.environ.get("EDITOR_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        base = base_url or os.environ.get("EDITOR_BASE_URL")
        if key:
            base = base or OPENROUTER_BASE_URL
        else:
            key, base = os.environ.get("OPENAI_API_KEY"), base or os.environ.get("OPENAI_BASE_URL")
        if not key:
            raise RuntimeError("no editor API key: set OPENROUTER_API_KEY (or OPENAI_API_KEY) in .env")

        self.model = model
        self.base_url = base
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self._client = AsyncOpenAI(api_key=key, base_url=base, max_retries=0)
        self._sem = asyncio.Semaphore(concurrency)
        self._lock = asyncio.Lock()
        self._cache_path = Path(cache_path) if cache_path else None
        self._cache: dict[str, str] = {}
        if self._cache_path and self._cache_path.exists():
            with open(self._cache_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._cache[r["key"]] = r["response"]
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.n_calls = 0
        self.n_cached = 0

    def _key(self, system: str, user: str, temperature: float) -> str:
        blob = f"{self.model}\x00{temperature}\x00{system}\x00{user}".encode()
        return hashlib.sha256(blob).hexdigest()[:32]

    async def call(self, system: str, user: str, temperature: float = 0.3) -> str:
        if getattr(self, "temperature_override", None) is not None:
            temperature = float(self.temperature_override)  # multi-constraint experiment pins T = 0
        key = self._key(system, user, temperature)
        if key in self._cache:
            self.n_cached += 1
            return self._cache[key]

        last: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with self._sem:
                    resp = await self._client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        temperature=temperature,
                        max_tokens=self.max_tokens,
                    )
                content = resp.choices[0].message.content
                if not content or not content.strip():
                    raise ValueError("empty editor response")
                content = content.strip()
                async with self._lock:
                    self._cache[key] = content
                    if self._cache_path:
                        with open(self._cache_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps({"key": key, "response": content}, ensure_ascii=False) + "\n")
                self.n_calls += 1
                return content
            except Exception as e:  # noqa: BLE001
                last = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(min(2**attempt, 20))
        raise RuntimeError(f"editor failed after {self.max_retries} attempts: {last}")
