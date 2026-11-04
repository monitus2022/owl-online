"""On-disk cache for model calls, keyed by (name, input)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

from app.providers.contracts import Llm


class CachedLlm:
    """Llm wrapper caching generate() by (name, input) on disk (AGENTS.md)."""

    def __init__(self, inner: Llm, name: str, cache_dir: Path) -> None:
        self.name = name
        self._inner = inner
        self._dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, system: str, prompt: str, *, context: str | None = None) -> str:
        key = hashlib.sha256(
            json.dumps([self.name, system, prompt, context]).encode("utf-8")
        ).hexdigest()
        path = self._dir / f"{key}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8")
        output = await self._inner.generate(system, prompt, context=context)
        path.write_text(output, encoding="utf-8")
        return output

    def stream(
        self, system: str, prompt: str, *, context: str | None = None
    ) -> AsyncIterator[str]:
        # Not cached: the eval only calls generate(); stream is passed through.
        return self._inner.stream(system, prompt, context=context)