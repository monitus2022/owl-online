"""Bounded per-book retrieval, no network."""

import asyncio

import pytest

from app.pipeline.retrieve.multibook import MAX_BOOKS, retrieve_multi_book
from app.schemas import Chunk, ChunkMetadata


def _chunk(chunk_id: str, book: int, score: float) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=f"Book {book}",
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=1,
            book_name=f"Book {book}",
            chapter_name="Chapter 1",
        ),
        score=score,
    )


class _BookRetriever:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    async def retrieve_book(self, query: str, book_num: int, top_k: int):
        self.calls.append((book_num, top_k))
        return [_chunk(f"b{book_num}-c01-0000", book_num, book_num / 10)]


async def test_retrieve_multi_book_covers_every_book_and_sorts():
    retriever = _BookRetriever()
    chunks = await retrieve_multi_book(retriever, "q", per_book_k=2)
    assert [call[0] for call in retriever.calls] == list(range(1, MAX_BOOKS + 1))
    assert all(call[1] == 2 for call in retriever.calls)
    assert [chunk.metadata.book_num for chunk in chunks] == list(
        range(MAX_BOOKS, 0, -1)
    )


async def test_retrieve_multi_book_caps_books_at_seven():
    calls: list[int] = []

    class _CountingRetriever:
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            calls.append(book_num)
            return [_chunk("same", book_num, 1.0)]

    chunks = await retrieve_multi_book(
        _CountingRetriever(), "q", books=range(1, 20)
    )
    assert calls == list(range(1, MAX_BOOKS + 1))
    assert len(chunks) == 1
    assert chunks[0].id == "same"


async def test_retrieve_multi_book_keeps_the_highest_scored_duplicate():
    class _DuplicateRetriever:
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            return [_chunk("same", book_num, float(book_num))]

    chunks = await retrieve_multi_book(_DuplicateRetriever(), "q")
    assert len(chunks) == 1
    assert chunks[0].score == float(MAX_BOOKS)


async def test_retrieve_multi_book_skips_a_failed_book():
    class _FlakyRetriever:
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            if book_num == 3:
                raise RuntimeError("book 3 failed")
            return [_chunk(f"b{book_num}-c01-0000", book_num, 1.0)]

    chunks = await retrieve_multi_book(_FlakyRetriever(), "q")
    assert {chunk.metadata.book_num for chunk in chunks} == {1, 2, 4, 5, 6, 7}


async def test_retrieve_multi_book_respects_the_fanout():
    class _ConcurrencyRetriever:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0

        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return [_chunk(f"b{book_num}-c01-0000", book_num, 1.0)]

    retriever = _ConcurrencyRetriever()
    await retrieve_multi_book(retriever, "q", fanout=2)
    assert retriever.max_active == 2


async def test_retrieve_multi_book_rejects_bad_limits():
    retriever = _BookRetriever()
    with pytest.raises(ValueError, match="per_book_k"):
        await retrieve_multi_book(retriever, "q", per_book_k=0)
    with pytest.raises(ValueError, match="fanout"):
        await retrieve_multi_book(retriever, "q", fanout=0)
