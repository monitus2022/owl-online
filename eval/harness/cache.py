"""On-disk cache for model calls, keyed by (name, input)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from pathlib import Path

from app.providers.contracts import Llm


class CachedLlm:
    """Llm wrapper caching generate() by (name, input) on disk (AGENTS.md)."""

    def __init__(
        self,
        inner: Llm | None,
        name: str,
        cache_dir: Path,
        *,
        variant: str | None = None,
    ) -> None:
        self.name = name
        self._inner = inner
        self._dir = cache_dir
        self._variant = variant
        cache_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, system: str, prompt: str, *, context: str | None = None) -> str:
        path = self._path(system, prompt, context)
        cached = self.get_cached(system, prompt, context=context)
        if cached is not None:
            return cached
        if self._inner is None:
            raise RuntimeError("cache-only CachedLlm cannot generate")
        output = await self._inner.generate(system, prompt, context=context)
        path.write_text(output, encoding="utf-8")
        return output

    def get_cached(
        self, system: str, prompt: str, *, context: str | None = None
    ) -> str | None:
        """Return a cached reply without calling the model, or None."""
        path = self._path(system, prompt, context)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _path(self, system: str, prompt: str, context: str | None) -> Path:
        key = hashlib.sha256(
            json.dumps([self.name, self._variant, system, prompt, context]).encode(
                "utf-8"
            )
        ).hexdigest()
        return self._dir / f"{key}.txt"

    def stream(
        self, system: str, prompt: str, *, context: str | None = None
    ) -> AsyncIterator[str]:
        # Not cached: the eval only calls generate(); stream is passed through.
        return self._inner.stream(system, prompt, context=context)