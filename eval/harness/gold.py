"""Gold set: one question per item, with evidence ids and a short answer."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GoldItem:
    """One gold question; expected_chunk_ids is empty for unanswerable items."""

    id: str
    question: str
    answerable: bool
    expected_chunk_ids: list[str]
    slices: tuple[str, ...] = ()
    reference_answer: str = ""
    reason: str = ""

    @property
    def primary_slice(self) -> str:
        """The slice a metric is filed under; labels in the gold set are disjoint."""
        if self.slices:
            return self.slices[0]
        return "simple" if self.answerable else "off_topic"


def load_gold(path: Path) -> list[GoldItem]:
    """Read the gold JSONL into GoldItem records."""
    items: list[GoldItem] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        items.append(
            GoldItem(
                id=row["id"],
                question=row["question"],
                answerable=bool(row["answerable"]),
                expected_chunk_ids=list(row.get("expected_chunk_ids", [])),
                slices=tuple(row.get("slices", [])),
                reference_answer=str(row.get("reference_answer", "")),
                reason=str(row.get("reason", "")),
            )
        )
    return items