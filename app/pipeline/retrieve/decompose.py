"""Split a multi-part question into at most three sub-queries."""

from __future__ import annotations

import re

_WH = re.compile(r"\b(what|who|which|where|when|why|how)\b", re.I)
_SPLIT = re.compile(r"\s*;\s*|\s+and\s+", re.I)
MAX_SUB_QUERIES = 3


def split_question(query: str) -> list[str]:
    """Return one or more sub-queries, capped at three.

    A split is accepted only when every part still looks like a question, so
    phrases such as "the difference between X and Y" stay intact.
    """
    text = query.strip()
    if "?" not in text:
        return [text]
    parts = [part.strip(" ?") for part in _SPLIT.split(text) if part.strip(" ?")]
    if len(parts) < 2 or not all(_WH.search(part) for part in parts):
        return [text]
    return [f"{part}?" for part in parts[:MAX_SUB_QUERIES]]
