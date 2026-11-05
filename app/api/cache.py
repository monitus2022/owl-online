"""Exact answer cache for corpus-only chat answers.

The key carries the prompt version, index hash, model and normalised question.
Practice and feedback never reach it: feedback is personalised by the student
answer, and practice is meant to vary.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from collections.abc import Callable

from app.pipeline.generate import RETRY_SYSTEM_PROMPT, SYSTEM_PROMPT, AskResult

PROMPT_VERSION = hashlib.sha256(
    f"{SYSTEM_PROMPT}\n{RETRY_SYSTEM_PROMPT}".encode()
).hexdigest()[:12]

_PUNCTUATION = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")


def normalize_question(question: str) -> str:
    """Lowercase, drop punctuation and collapse whitespace."""
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", question.lower())).strip()


def cache_key(question: str, index_hash: str, model: str) -> str:
    """Stable key for the exact cache."""
    material = "\n".join(
        [PROMPT_VERSION, index_hash, model, normalize_question(question)]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AnswerCache:
    """Bounded LRU with a TTL, in process memory."""

    def __init__(
        self,
        max_entries: int = 256,
        ttl_s: int = 3600,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_entries
        self._ttl = ttl_s
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, AskResult]] = OrderedDict()

    def get(self, key: str) -> AskResult | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, result = entry
        if self._clock() - stored_at > self._ttl:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return result

    def put(self, key: str, result: AskResult) -> None:
        self._entries[key] = (self._clock(), result)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
