"""Lore pack: authored setting facts with their own citations.

The books are the primary corpus. The lore pack holds product canon: the school,
the professor, the curriculum, the exam format and the timeline. It is raw text
loaded from a private path and selected by subject, tag and keyword. No
embeddings, so a setting edit is a text edit plus a reload.

Each entry carries a canonicity tier:

- `book`: a fact that also appears in the seven books;
- `product`: authored product canon, reviewed by a human;
- `secondary`: a secondary reference used only for authoring.

The next ticket wires lore into the answer path. When it lands, answers will
cite book chunks as `[b1-c01-0000]` and lore entries as `[lore:school-001]`; the
two id spaces never overlap. Until then the schema, loader and fixture are in
place, and the answer path stays book-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Reserved for the next ticket, when lore citations join the answer path.
LORE_CITATION = re.compile(r"\[lore:([a-z0-9][a-z0-9-]*)\]")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TIERS = frozenset({"book", "product", "secondary"})
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "your",
        "with",
        "what",
        "who",
        "how",
        "does",
        "did",
        "was",
        "were",
        "this",
        "that",
        "from",
        "have",
        "has",
        "about",
        "into",
        "they",
        "their",
        "there",
        "which",
        "when",
        "where",
        "will",
        "would",
        "can",
        "could",
    }
)


@dataclass(frozen=True)
class LoreEntry:
    """One authored setting fact."""

    id: str
    subject: str
    tier: str
    title: str
    body: str
    source: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoreStore:
    """A loaded lore pack, with keyword selection and id lookup."""

    entries: tuple[LoreEntry, ...]
    by_id: dict[str, LoreEntry]

    def get(self, entry_id: str) -> LoreEntry | None:
        return self.by_id.get(entry_id)

    def ids(self) -> set[str]:
        return set(self.by_id)

    def select(
        self, question: str, *, subject: str | None = None, limit: int = 3
    ) -> list[LoreEntry]:
        """Return the entries that share the most terms with the question."""
        query = _tokens(question)
        if not query:
            return []
        scored: list[tuple[int, LoreEntry]] = []
        for entry in self.entries:
            if subject is not None and entry.subject not in (subject, "all"):
                continue
            haystack = _tokens(
                " ".join((entry.title, entry.body, " ".join(entry.tags)))
            )
            score = len(query & haystack)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda item: (-item[0], item[1].id))
        return [entry for _, entry in scored[: max(1, limit)]]


def _tokens(text: str) -> set[str]:
    return {
        word
        for word in _WORD.findall(text.casefold())
        if len(word) > 2 and word not in _STOP
    }


def _require(row: dict, key: str, line_number: int) -> object:
    if key not in row:
        raise ValueError(f"lore line {line_number}: missing {key!r}")
    return row[key]


def load_lore(path: Path) -> LoreStore:
    """Read and validate a lore JSONL file.

    Fails loudly on a duplicate id, an unknown tier or an empty body: a broken
    setting pack should stop the app, not produce a quietly wrong answer.
    """
    entries: list[LoreEntry] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"lore line {line_number}: expected a JSON object")
        entry_id = str(_require(row, "id", line_number)).strip()
        if not _ID.match(entry_id):
            raise ValueError(
                f"lore line {line_number}: id must be lowercase letters, digits "
                f"and hyphens, got {entry_id!r}"
            )
        if entry_id in seen:
            raise ValueError(f"lore line {line_number}: duplicate id {entry_id!r}")
        seen.add(entry_id)
        tier = str(_require(row, "tier", line_number))
        if tier not in TIERS:
            raise ValueError(
                f"lore line {line_number}: tier must be one of {sorted(TIERS)}, "
                f"got {tier!r}"
            )
        body = str(_require(row, "body", line_number)).strip()
        if not body:
            raise ValueError(f"lore line {line_number}: empty body")
        subject = str(_require(row, "subject", line_number)).strip()
        if not subject:
            raise ValueError(f"lore line {line_number}: empty subject")
        title = str(_require(row, "title", line_number)).strip()
        if not title:
            raise ValueError(f"lore line {line_number}: empty title")
        source = str(_require(row, "source", line_number)).strip()
        if not source:
            raise ValueError(f"lore line {line_number}: empty source")
        tags = row.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"lore line {line_number}: tags must be a list of strings")
        entries.append(
            LoreEntry(
                id=entry_id,
                subject=subject,
                tier=tier,
                title=title,
                body=body,
                source=source,
                tags=tuple(tag.strip() for tag in tags),
            )
        )
    if not entries:
        raise ValueError(f"no lore entries in {path}")
    return LoreStore(tuple(entries), {entry.id: entry for entry in entries})
