"""Bounded per-book retrieval, no network."""

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


async def test_retrieve_multi_book_deduplicates_and_caps_books():
    class _DuplicateRetriever:
        async def retrieve_book(self, query: str, book_num: int, top_k: int):
            return [_chunk("same", book_num, 1.0)]

    chunks = await retrieve_multi_book(
        _DuplicateRetriever(), "q", books=range(1, 20)
    )
    assert len(chunks) == 1
    assert chunks[0].id == "same"


async def test_retrieve_multi_book_rejects_bad_limits():
    retriever = _BookRetriever()
    try:
        await retrieve_multi_book(retriever, "q", per_book_k=0)
    except ValueError as error:
        assert "per_book_k" in str(error)
    else:
        raise AssertionError("per_book_k=0 should fail")

    try:
        await retrieve_multi_book(retriever, "q", fanout=0)
    except ValueError as error:
        assert "fanout" in str(error)
    else:
        raise AssertionError("fanout=0 should fail")
