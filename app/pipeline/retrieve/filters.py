"""Parse explicit book and chapter references into a metadata filter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

_UNITS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}
_TEENS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50}
_NUMBER_WORD = r"(\d+|[a-z]+(?:-[a-z]+)?)"
_BOOKS = {
    "philosopher's stone": 1,
    "sorcerer's stone": 1,
    "chamber of secrets": 2,
    "prisoner of azkaban": 3,
    "goblet of fire": 4,
    "order of the phoenix": 5,
    "half-blood prince": 6,
    "deathly hallows": 7,
}
_BOOK_NUM = re.compile(rf"\bbook\s+{_NUMBER_WORD}\b", re.I)
_CHAPTER_NUM = re.compile(rf"\bchapter\s+{_NUMBER_WORD}\b", re.I)


def _number(raw: str) -> int | None:
    value = raw.strip().lower()
    if value.isdigit():
        return int(value)
    parts = value.replace("-", " ").split()
    if len(parts) == 1:
        part = parts[0]
        for table in (_UNITS, _TEENS, _TENS):
            if part in table:
                return table[part]
        return None
    if len(parts) == 2:
        tens = _TENS.get(parts[0])
        units = _UNITS.get(parts[1])
        if tens is not None and units is not None:
            return tens + units
    return None


@dataclass(frozen=True)
class MetadataFilter:
    """A parsed book/chapter constraint; either side may be absent."""

    book_num: int | None = None
    chapter_num: int | None = None
    explicit: bool = field(default=False, compare=False)

    def chroma_where(self) -> dict | None:
        clauses: list[dict] = []
        if self.book_num is not None:
            clauses.append({"book_num": {"$eq": self.book_num}})
        if self.chapter_num is not None:
            clauses.append({"chapter_num": {"$eq": self.chapter_num}})
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def matches(self, metadata: Mapping) -> bool:
        if self.book_num is not None and metadata.get("book_num") != self.book_num:
            return False
        if self.chapter_num is not None and metadata.get("chapter_num") != self.chapter_num:
            return False
        return True


def parse_metadata_filter(query: str) -> MetadataFilter | None:
    """Extract numeric or named book/chapter references from a question.

    `explicit` is true for a numeric reference or a title followed by "book" or
    "chapter". A bare title such as "Chamber of Secrets" may be an in-world name,
    so it still filters but does not relax the lexical abstention gate.
    """
    text = query.lower().replace("\u2019", "'")
    book_match = _BOOK_NUM.search(text)
    chapter_match = _CHAPTER_NUM.search(text)
    book_num = _number(book_match.group(1)) if book_match else None
    chapter_num = _number(chapter_match.group(1)) if chapter_match else None
    explicit = book_match is not None or chapter_match is not None
    if book_num is None:
        for name, number in _BOOKS.items():
            if re.search(rf"\b{re.escape(name)}\s+(?:book|chapter)\b", text):
                book_num = number
                explicit = True
                break
    if book_num is None:
        for name, number in _BOOKS.items():
            if name in text:
                book_num = number
                break
    if book_num is None and chapter_num is None:
        return None
    return MetadataFilter(
        book_num=book_num, chapter_num=chapter_num, explicit=explicit
    )
