"""Deterministic fabrication signal: capitalized names absent from the corpus.

Not a correctness check: it catches invented entities, not a real name used
wrongly. Corpus scope avoids false positives on aliases and morphology.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas import Chunk

_CITATION = re.compile(r"\[[^\]]*\]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")
# Keep a hyphenated name together: "Time-Turner" must not report "Turner".
_ENTITY = re.compile(r"\b[A-Z][a-z]{2,}(?:-[A-Z][a-z]{2,})?\b")


def corpus_vocabulary(chunks: list[Chunk]) -> set[str]:
    """Lowercased word forms that appear anywhere in the corpus."""
    return {word.lower() for chunk in chunks for word in _WORD.findall(chunk.text)}


def novel_entities(answer: str, vocabulary: set[str]) -> list[str]:
    """Capitalized answer tokens that the corpus never uses, in order, unique."""
    text = _CITATION.sub(" ", answer)
    found: list[str] = []
    for match in _ENTITY.finditer(text):
        token = match.group(0)
        before = text[: match.start()].rstrip()
        if not before or before[-1] in ".!?":
            # A sentence-initial capital is grammar, not evidence of a name.
            continue
        if token.lower() in vocabulary or token in found:
            continue
        found.append(token)
    return found


@dataclass(frozen=True)
class NoveltyMetrics:
    """Answers with at least one out-of-corpus entity, and the tokens seen."""

    n: int
    flagged: int
    tokens: tuple[str, ...] = ()

    @property
    def rate(self) -> float:
        return self.flagged / self.n if self.n else 0.0


def summarize_novelty(
    answers: list[str], vocabulary: set[str]
) -> NoveltyMetrics:
    flagged = 0
    tokens: list[str] = []
    for answer in answers:
        found = novel_entities(answer, vocabulary)
        if found:
            flagged += 1
            tokens.extend(found)
    return NoveltyMetrics(len(answers), flagged, tuple(dict.fromkeys(tokens)))
