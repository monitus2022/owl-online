"""Deterministic retrieval strategy: single-hop or multi-book coverage.

The router uses pre-retrieval scope cues, not a model call. A plural count alone
is not a coverage cue: "the three Deathly Hallows" is a single-book question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

StrategyName = Literal["single_hop", "multi_book"]

# Ordered so the first matching cue becomes the reason. Each cue is a phrase
# that asks for coverage across books, not merely a plural count.
_COVERAGE_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("each", re.compile(r"\beach (?:book|of the|of)\b", re.I)),
    ("every", re.compile(r"\bevery (?:single )?(?:book|one of the)\b", re.I)),
    ("all_seven", re.compile(r"\ball seven\b", re.I)),
    ("across", re.compile(r"\bacross (?:all|the books|books|the series)\b", re.I)),
    ("which_books", re.compile(r"\bwhich books?\b", re.I)),
    ("in_which_books", re.compile(r"\bin which books?\b", re.I)),
    ("list_all", re.compile(r"\blist all\b", re.I)),
    ("for_each", re.compile(r"\bfor each\b", re.I)),
    ("per_book", re.compile(r"\bper book\b", re.I)),
)
_PLURAL_COUNT = re.compile(r"\b(two|three|four|five|six|seven)\b", re.I)
_BOOK_LIST = re.compile(r"\bbooks?\s+((?:\d+\s*(?:,|and|&)?\s*)+)", re.I)


@dataclass(frozen=True)
class RetrievalStrategy:
    """The chosen retrieval strategy plus the cue that decided it."""

    name: StrategyName
    reason: str
    cues: tuple[str, ...] = ()

    @property
    def is_multi_book(self) -> bool:
        return self.name == "multi_book"


def classify_retrieval_strategy(question: str) -> RetrievalStrategy:
    """Classify a question from deterministic scope cues.

    Explicit multiple book numbers win first. Then a coverage phrase. A plural
    count without a coverage phrase stays single-hop, which is the near-miss
    case the fixture measures.
    """
    text = question.strip()
    book_numbers = {
        int(number) for number in re.findall(r"\bbooks?\s+(\d+)", text)
    }
    book_match = _BOOK_LIST.search(text)
    if book_match:
        book_numbers.update(
            int(number) for number in re.findall(r"\d+", book_match.group(1))
        )
    if len(book_numbers) >= 2:
        return RetrievalStrategy(
            "multi_book",
            f"multiple_book_numbers:{len(book_numbers)}",
            tuple(str(number) for number in sorted(book_numbers)),
        )

    cues = tuple(name for name, pattern in _COVERAGE_CUES if pattern.search(text))
    if cues:
        return RetrievalStrategy("multi_book", f"coverage_cue:{cues[0]}", cues)

    plural = _PLURAL_COUNT.search(text)
    if plural is not None:
        return RetrievalStrategy(
            "single_hop",
            f"plural_count_without_coverage_cue:{plural.group(1).lower()}",
        )
    return RetrievalStrategy("single_hop", "no_coverage_cue")
