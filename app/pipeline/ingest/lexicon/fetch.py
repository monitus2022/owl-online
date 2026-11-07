"""Polite cached fetcher for the Lexicon harvest (#126).

Rules from docs/lexicon-canon-index.md: one request per second plus jitter,
a project User-Agent, cache by url, never refetch on a cache hit, retry once
with a backoff, and record the fetch date and response hash next to every
page. Network and clock are injected so tests run offline.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "owl-online-research/0.1 (subject-pack mapping; contact: repository owner)"


def page_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")


@dataclass(frozen=True)
class FetchResult:
    url: str
    path: str
    from_cache: bool
    fetched_at: str  # ISO-8601 UTC
    sha256: str


class Fetcher:
    """Cache-first fetcher with one retry and injectable transport."""

    def __init__(
        self,
        cache_dir: Path,
        opener: Callable[[str], bytes],
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        politeness_s: float = 1.0,
        jitter_s: float = 0.4,
    ) -> None:
        self.cache_dir = cache_dir
        self.opener = opener
        self.sleep = sleep
        self.clock = clock
        self.politeness_s = politeness_s
        self.jitter_s = jitter_s

    def fetch(self, url: str) -> tuple[FetchResult, str]:
        """Return (record, html). Cache hits cost no request and no sleep."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = page_path(self.cache_dir, url)
        if path.exists():
            html = path.read_text(encoding="utf-8", errors="replace")
            return (
                FetchResult(
                    url=url,
                    path=str(path),
                    from_cache=True,
                    fetched_at="",
                    sha256=hashlib.sha256(html.encode("utf-8", "replace")).hexdigest(),
                ),
                html,
            )
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                body = self.opener(url)
            except Exception as error:  # transport boundary: retry once, then raise
                last_error = error
                if attempt == 1:
                    self.sleep(5.0)
                    continue
                raise RuntimeError(f"fetch failed after retry: {url}") from last_error
            html = body.decode("utf-8", errors="replace")
            path.write_text(html, encoding="utf-8")
            # Stable pseudo-jitter from the url hash: polite, reproducible.
            jitter = int(path.stem[-4:], 16) % 100 / 100.0
            self.sleep(self.politeness_s + self.jitter_s * jitter)
            return (
                FetchResult(
                    url=url,
                    path=str(path),
                    from_cache=False,
                    fetched_at=self.clock().isoformat(timespec="seconds"),
                    sha256=hashlib.sha256(body).hexdigest(),
                ),
                html,
            )
        raise AssertionError("unreachable")  # pragma: no cover
