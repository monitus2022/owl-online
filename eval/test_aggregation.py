"""Aggregation fixture shape, scoring and metrics, no network."""

import json
from pathlib import Path

import pytest

from app.schemas import Chunk, ChunkMetadata
from eval.harness import (
    AggregationItem,
    BookExpectation,
    aggregation_metrics,
    entity_matches,
    load_aggregation,
    score_item,
    summarize_aggregation,
)

FIXTURE = Path(__file__).with_name("fixtures") / "aggregation.jsonl"


def _chunk(chunk_id: str, book: int, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=1,
            book_name=f"Book {book}",
            chapter_name="Chapter 1",
        ),
    )


def test_fixture_keeps_the_pinned_shape():
    items = load_aggregation(FIXTURE)
    assert len(items) == 15
    assert sum(item.kind == "multi_book" for item in items) == 10
    assert sum(item.kind == "near_miss" for item in items) == 5
    assert len({item.id for item in items}) == 15
    assert all(1 <= book.book_num <= 7 for item in items for book in item.books)
    assert all(len(item.books) >= 2 for item in items if item.kind == "multi_book")
    assert all(len(item.books) == 1 for item in items if item.kind == "near_miss")
    assert all(
        entity.strip()
        for item in items
        for book in item.books
        for entity in book.expected_entities
    )


def test_loader_rejects_a_multi_book_item_with_one_book(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "bad",
                "question": "q",
                "kind": "multi_book",
                "books": [{"book_num": 1, "expected_entities": ["x"]}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="at least two books"):
        load_aggregation(path)


def test_loader_rejects_duplicate_ids(tmp_path):
    row = {
        "id": "dup",
        "question": "q",
        "kind": "near_miss",
        "books": [{"book_num": 1, "expected_entities": ["x"]}],
    }
    path = tmp_path / "bad.jsonl"
    path.write_text(
        "\n".join(json.dumps(row) for _ in range(2)) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate aggregation id"):
        load_aggregation(path)


def test_loader_rejects_a_near_miss_with_two_books(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "bad",
                "question": "q",
                "kind": "near_miss",
                "books": [
                    {"book_num": 1, "expected_entities": ["x"]},
                    {"book_num": 2, "expected_entities": ["y"]},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one book"):
        load_aggregation(path)


def test_entity_match_is_case_insensitive_substring():
    assert entity_matches("Professor Quirrell teaches", "quirrell")
    assert entity_matches("the Horcruxes are", "Horcrux")
    assert not entity_matches("Lockhart", "Lupin")


def test_score_item_counts_books_entities_and_citations():
    item = AggregationItem(
        id="a",
        question="q",
        kind="multi_book",
        books=(
            BookExpectation(1, ("Quirrell",)),
            BookExpectation(2, ("Lockhart",)),
        ),
    )
    chunks = [
        _chunk("b1-c01-0001", 1, "Quirrell teaches Defence."),
        _chunk("b2-c01-0001", 2, "Lockhart teaches Defence."),
        _chunk("b3-c01-0001", 3, "An extra book."),
    ]
    score = score_item(item, chunks)
    assert score.expected_books == 2
    assert score.covered_books == 2
    assert score.expected_entities == 2
    assert score.found_entities == 2
    assert score.citations == 3
    assert score.valid_citations == 2


def test_score_item_marks_a_missing_book_and_entity():
    item = AggregationItem(
        id="a",
        question="q",
        kind="multi_book",
        books=(
            BookExpectation(1, ("Quirrell",)),
            BookExpectation(2, ("Lockhart",)),
        ),
    )
    score = score_item(item, [_chunk("b1-c01-0001", 1, "Quirrell teaches.")])
    assert score.covered_books == 1
    assert score.found_entities == 1
    assert score.expected_entities == 2
    assert score.valid_citations == 1


def test_summarize_aggregation_separates_multi_and_near():
    multi = score_item(
        AggregationItem(
            id="a",
            question="q",
            kind="multi_book",
            books=(
                BookExpectation(1, ("Quirrell",)),
                BookExpectation(2, ("Lockhart",)),
            ),
        ),
        [
            _chunk("b1-c01-0001", 1, "Quirrell teaches."),
            _chunk("b2-c01-0001", 2, "Lockhart teaches."),
        ],
    )
    near = score_item(
        AggregationItem(
            id="n",
            question="q",
            kind="near_miss",
            books=(BookExpectation(4, ("Durmstrang",)),),
        ),
        [
            _chunk("b4-c01-0001", 4, "Durmstrang arrives."),
            _chunk("b5-c01-0001", 5, "An extra book."),
        ],
    )
    metrics = summarize_aggregation([multi, near])
    assert metrics.n_multi == 1
    assert metrics.n_near == 1
    assert metrics.book_coverage == 1.0
    assert metrics.entity_completeness == 1.0
    assert metrics.full_coverage_rate == 1.0
    assert metrics.near_miss_entity_hit == 1.0
    assert metrics.near_miss_book_precision == 0.5
    assert metrics.citation_validity == 0.75


async def test_aggregation_metrics_retrieves_once_per_item():
    item = AggregationItem(
        id="a",
        question="q",
        kind="multi_book",
        books=(
            BookExpectation(1, ("Quirrell",)),
            BookExpectation(2, ("Lockhart",)),
        ),
    )

    class _FakeRetriever:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
            self.calls.append(query)
            return [
                _chunk("b1-c01-0001", 1, "Quirrell teaches."),
                _chunk("b2-c01-0001", 2, "Lockhart teaches."),
            ][:top_k]

    retriever = _FakeRetriever()
    scores, metrics = await aggregation_metrics(retriever, [item], k=5)
    assert retriever.calls == ["q"]
    assert scores[0].covered_books == 2
    assert metrics.book_coverage == 1.0
