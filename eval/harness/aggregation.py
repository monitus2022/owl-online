"""Aggregation fixture: per-book coverage instead of one reference answer.

A multi-book question is scored on whether retrieval reached each expected book
and found the expected entity there. A near-miss is scored on staying inside its
single book, so a plural count alone cannot make a question look multi-book.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from app.providers.contracts import Retriever
from app.schemas import Chunk

AggregationKind = Literal["multi_book", "near_miss"]
_FRONT_MATTER = re.compile(r"\bCONTENTS\b|All rights reserved|ISBN", re.I)


def _is_front_matter(text: str) -> bool:
    """Table-of-contents and copyright pages are not narrative evidence."""
    return _FRONT_MATTER.search(text) is not None


@dataclass(frozen=True)
class BookExpectation:
    """One book and the entities a correct answer must cover there."""

    book_num: int
    expected_entities: tuple[str, ...]


@dataclass(frozen=True)
class AggregationItem:
    """One multi-book question or one plural-sounding near-miss."""

    id: str
    question: str
    kind: AggregationKind
    books: tuple[BookExpectation, ...]
    notes: str = ""


@dataclass(frozen=True)
class AggregationScore:
    """Per-item retrieval outcome for the aggregation fixture."""

    item_id: str
    kind: AggregationKind
    expected_books: int
    covered_books: int
    expected_entities: int
    found_entities: int
    citations: int
    valid_citations: int


@dataclass(frozen=True)
class AggregationMetrics:
    """Aggregate coverage, completeness and citation validity."""

    n_multi: int
    n_near: int
    book_coverage: float
    entity_completeness: float
    citation_validity: float
    full_coverage_rate: float
    near_miss_entity_hit: float
    near_miss_entity_completeness: float
    near_miss_book_share: float


def _require(row: dict, key: str, line_number: int):
    if key not in row:
        raise ValueError(f"line {line_number}: missing {key!r}")
    return row[key]


def _check_book(book: BookExpectation, item_id: str) -> None:
    if not 1 <= book.book_num <= 7:
        raise ValueError(f"{item_id}: book_num must be 1..7, got {book.book_num}")
    if not book.expected_entities:
        raise ValueError(f"{item_id}: book {book.book_num} has no expected entities")
    if any(not entity.strip() for entity in book.expected_entities):
        raise ValueError(f"{item_id}: empty expected entity")


def load_aggregation(path: Path) -> list[AggregationItem]:
    """Read and validate the aggregation JSONL."""
    items: list[AggregationItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"line {line_number}: expected a JSON object")
        item_id = str(_require(row, "id", line_number)).strip()
        if not item_id:
            raise ValueError(f"line {line_number}: empty id")
        if item_id in seen:
            raise ValueError(f"duplicate aggregation id: {item_id}")
        seen.add(item_id)
        question = str(_require(row, "question", line_number)).strip()
        if not question:
            raise ValueError(f"{item_id}: empty question")
        kind = str(_require(row, "kind", line_number))
        if kind not in {"multi_book", "near_miss"}:
            raise ValueError(f"{item_id}: unknown kind {kind!r}")
        raw_books = _require(row, "books", line_number)
        if not isinstance(raw_books, list) or not raw_books:
            raise ValueError(f"{item_id}: books must be a non-empty list")
        books: list[BookExpectation] = []
        for raw_book in raw_books:
            if not isinstance(raw_book, dict):
                raise ValueError(f"{item_id}: each book must be an object")
            if "book_num" not in raw_book:
                raise ValueError(f"{item_id}: book is missing book_num")
            if "expected_entities" not in raw_book:
                raise ValueError(f"{item_id}: book is missing expected_entities")
            entities = raw_book["expected_entities"]
            if not isinstance(entities, list) or not entities:
                raise ValueError(f"{item_id}: expected_entities must be a non-empty list")
            books.append(
                BookExpectation(
                    book_num=int(raw_book["book_num"]),
                    expected_entities=tuple(str(entity) for entity in entities),
                )
            )
        if kind == "multi_book" and len(books) < 2:
            raise ValueError(f"{item_id}: multi_book needs at least two books")
        if kind == "near_miss" and len(books) != 1:
            raise ValueError(f"{item_id}: near_miss needs exactly one book")
        if len({book.book_num for book in books}) != len(books):
            raise ValueError(f"{item_id}: duplicate book_num")
        for book in books:
            _check_book(book, item_id)
        items.append(
            AggregationItem(
                id=item_id,
                question=question,
                kind=cast(AggregationKind, kind),
                books=tuple(books),
                notes=str(row.get("notes", "")),
            )
        )
    if not items:
        raise ValueError(f"no aggregation items in {path}")
    return items


def entity_matches(text: str, entity: str) -> bool:
    """Word-boundary, plural-friendly match; entities are names, not regexes."""
    pattern = rf"\b{re.escape(entity)}\w*"
    return re.search(pattern, text, re.IGNORECASE) is not None


def score_item(item: AggregationItem, chunks: list[Chunk]) -> AggregationScore:
    """Score one item's retrieved chunks against its per-book expectations."""
    by_book = {book.book_num: book for book in item.books}
    covered_books = 0
    expected_entities = 0
    found_entities = 0
    for book in item.books:
        book_chunks = [c for c in chunks if c.metadata.book_num == book.book_num]
        covered = False
        for entity in book.expected_entities:
            expected_entities += 1
            if any(entity_matches(c.text, entity) for c in book_chunks):
                found_entities += 1
                covered = True
        covered_books += int(covered)

    def is_relevant(chunk: Chunk) -> bool:
        book = by_book.get(chunk.metadata.book_num)
        return book is not None and any(
            entity_matches(chunk.text, entity) for entity in book.expected_entities
        )

    return AggregationScore(
        item_id=item.id,
        kind=item.kind,
        expected_books=len(item.books),
        covered_books=covered_books,
        expected_entities=expected_entities,
        found_entities=found_entities,
        citations=len(chunks),
        valid_citations=sum(is_relevant(chunk) for chunk in chunks),
    )


def summarize_aggregation(scores: list[AggregationScore]) -> AggregationMetrics:
    """Macro-average coverage and completeness, micro-average citation validity."""
    multi = [score for score in scores if score.kind == "multi_book"]
    near = [score for score in scores if score.kind == "near_miss"]
    multi_n = len(multi)
    near_n = len(near)
    citations = sum(score.citations for score in scores)
    valid = sum(score.valid_citations for score in scores)
    near_citations = sum(score.citations for score in near)
    near_valid = sum(score.valid_citations for score in near)
    return AggregationMetrics(
        n_multi=multi_n,
        n_near=near_n,
        book_coverage=(
            sum(score.covered_books / score.expected_books for score in multi) / multi_n
            if multi_n
            else 0.0
        ),
        entity_completeness=(
            sum(score.found_entities / score.expected_entities for score in multi)
            / multi_n
            if multi_n
            else 0.0
        ),
        citation_validity=valid / citations if citations else 0.0,
        full_coverage_rate=(
            sum(score.covered_books == score.expected_books for score in multi)
            / multi_n
            if multi_n
            else 0.0
        ),
        near_miss_entity_hit=(
            sum(score.found_entities > 0 for score in near) / near_n
            if near_n
            else 0.0
        ),
        near_miss_entity_completeness=(
            sum(score.found_entities / score.expected_entities for score in near)
            / near_n
            if near_n
            else 0.0
        ),
        near_miss_book_share=(
            near_valid / near_citations if near_citations else 0.0
        ),
    )


def missing_entities(
    items: list[AggregationItem], chunks: list[Chunk]
) -> list[str]:
    """Expected entities that do not appear in their book in the corpus."""
    by_book: dict[int, list[str]] = defaultdict(list)
    for chunk in chunks:
        if _is_front_matter(chunk.text):
            continue
        by_book[chunk.metadata.book_num].append(chunk.text)
    missing: list[str] = []
    for item in items:
        for book in item.books:
            for entity in book.expected_entities:
                if not any(
                    entity_matches(text, entity) for text in by_book[book.book_num]
                ):
                    missing.append(f"{item.id} book {book.book_num}: {entity!r}")
    return missing


async def aggregation_scores(
    retriever: Retriever, items: list[AggregationItem], k: int
) -> list[AggregationScore]:
    """Retrieve once per item and score the per-book outcome."""
    scores: list[AggregationScore] = []
    for item in items:
        chunks = await retriever.retrieve(item.question, k)
        scores.append(score_item(item, chunks))
    return scores


async def aggregation_metrics(
    retriever: Retriever, items: list[AggregationItem], k: int
) -> tuple[list[AggregationScore], AggregationMetrics]:
    """Per-item scores plus the aggregate metrics."""
    scores = await aggregation_scores(retriever, items, k)
    return scores, summarize_aggregation(scores)
