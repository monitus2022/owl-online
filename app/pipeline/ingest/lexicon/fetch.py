"""Polite cached fetcher for the Lexicon harvest (#126).

Rules from docs/lexicon-canon-index.md: one request per second plus jitter,
a project User-Agent, cache by url, never refetch on a cache hit, retry once
with a backoff, and record the fetch date and response hash next to every
page. Metadata lives in a sidecar `<key>.json` written at fetch time and
backfilled from the file mtime for caches predating it, so a re-parse never
loses the access date (#128 attribution needs it). Writes are atomic; an
empty cache file is a miss. Network and clock are injected so tests run
offline.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "owl-online-research/0.1 (subject-pack mapping; contact: repository owner)"


def page_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")


def meta_path(path: Path) -> Path:
    return path.with_suffix(".json")


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


@dataclass(frozen=True)
class FetchResult:
    url: str
    path: str
    from_cache: bool
    fetched_at: str  # ISO-8601 UTC
    sha256: str  # hash of the bytes as received


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

    def _meta(self, url: str, path: Path, html: str) -> tuple[str, str]:
        """The (fetched_at, sha256) pair: sidecar first, mtime backfill for
        caches that predate it, then persisted so re-parses never lose it."""
        sidecar = meta_path(path)
        if sidecar.exists():
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            return data["fetched_at"], data["sha256"]
        fetched_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(
            timespec="seconds"
        )
        sha256 = hashlib.sha256(html.encode("utf-8", "replace")).hexdigest()
        _write_atomic(
            sidecar, json.dumps({"url": url, "fetched_at": fetched_at, "sha256": sha256})
        )
        return fetched_at, sha256

    def fetch(self, url: str) -> tuple[FetchResult, str]:
        """Return (record, html). Cache hits cost no request and no sleep."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = page_path(self.cache_dir, url)
        if path.exists() and path.stat().st_size > 0:
            html = path.read_text(encoding="utf-8", errors="replace")
            fetched_at, sha256 = self._meta(url, path, html)
            return (
                FetchResult(
                    url=url,
                    path=str(path),
                    from_cache=True,
                    fetched_at=fetched_at,
                    sha256=sha256,
                ),
                html,
            )
        for attempt in (1, 2):
            try:
                body = self.opener(url)
            except Exception as error:  # transport boundary: retry once, then raise
                if attempt == 1:
                    self.sleep(5.0)
                    continue
                raise RuntimeError(f"fetch failed after retry: {url}") from error
            html = body.decode("utf-8", errors="replace")
            _write_atomic(path, html)
            fetched_at = self.clock().isoformat(timespec="seconds")
            sha256 = hashlib.sha256(body).hexdigest()
            meta = json.dumps({"url": url, "fetched_at": fetched_at, "sha256": sha256})
            _write_atomic(meta_path(path), meta)
            # Stable pseudo-jitter from the url hash: polite, reproducible.
            jitter = int(path.stem[-4:], 16) % 100 / 100.0
            self.sleep(self.politeness_s + self.jitter_s * jitter)
            return (
                FetchResult(
                    url=url,
                    path=str(path),
                    from_cache=False,
                    fetched_at=fetched_at,
                    sha256=sha256,
                ),
                html,
            )
        raise AssertionError("unreachable")  # pragma: no cover
