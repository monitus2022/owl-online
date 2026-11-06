"""Aggregation fixture: per-book coverage instead of one reference answer.

A multi-book question is scored on whether retrieval reached each expected book
and found the expected entity there. A near-miss is scored on staying inside its
single book, so a plural count alone cannot make a question look multi-book.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.providers.contracts import Retriever
from app.schemas import Chunk

AggregationKind = Literal["multi_book", "near_miss"]


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
    near_miss_book_precision: float


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
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        item_id = str(row["id"])
        if item_id in seen:
            raise ValueError(f"duplicate aggregation id: {item_id}")
        seen.add(item_id)
        kind = str(row["kind"])
        if kind not in {"multi_book", "near_miss"}:
            raise ValueError(f"{item_id}: unknown kind {kind!r}")
        books = tuple(
            BookExpectation(
                book_num=int(book["book_num"]),
                expected_entities=tuple(
                    str(entity) for entity in book["expected_entities"]
                ),
            )
            for book in row.get("books", [])
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
                question=str(row["question"]),
                kind=kind,  # type: ignore[arg-type]
                books=books,
                notes=str(row.get("notes", "")),
            )
        )
    if not items:
        raise ValueError(f"no aggregation items in {path}")
    return items


def entity_matches(text: str, entity: str) -> bool:
    """Case-insensitive substring match; entities are names, not regexes."""
    return entity.casefold() in text.casefold()


def score_item(item: AggregationItem, chunks: list[Chunk]) -> AggregationScore:
    """Score one item's retrieved chunks against its per-book expectations."""
    expected_books = {book.book_num for book in item.books}
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
        covered_books += covered
    valid_citations = sum(
        c.metadata.book_num in expected_books for c in chunks
    )
    return AggregationScore(
        item_id=item.id,
        kind=item.kind,
        expected_books=len(item.books),
        covered_books=covered_books,
        expected_entities=expected_entities,
        found_entities=found_entities,
        citations=len(chunks),
        valid_citations=valid_citations,
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
        near_miss_book_precision=(
            near_valid / near_citations if near_citations else 0.0
        ),
    )


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
