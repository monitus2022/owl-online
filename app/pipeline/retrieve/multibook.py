"""Bounded per-book retrieval for coverage questions.

One filtered retrieval per book, merged and deduplicated. This is the retrieval
half of the multi-book path; extraction and synthesis happen later.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from itertools import islice
from typing import Protocol

from app.schemas import Chunk

logger = logging.getLogger(__name__)

MAX_BOOKS = 7
DEFAULT_FANOUT = 4


class BookRetriever(Protocol):
    """A retriever that can restrict one pass to a single book."""

    async def retrieve_book(
        self, query: str, book_num: int, top_k: int
    ) -> list[Chunk]: ...


async def retrieve_multi_book(
    retriever: BookRetriever,
    query: str,
    *,
    per_book_k: int = 1,
    fanout: int = DEFAULT_FANOUT,
    books: Iterable[int] = range(1, MAX_BOOKS + 1),
) -> list[Chunk]:
    """Retrieve per book, merge, deduplicate and sort by score.

    The number of map calls is capped at `MAX_BOOKS` and the in-flight calls at
    `fanout`. `per_book_k` is the candidate count for each book, not the final
    list size; the caller decides how many merged chunks to keep.
    """
    if per_book_k < 1:
        raise ValueError("per_book_k must be at least 1")
    if fanout < 1:
        raise ValueError("fanout must be at least 1")
    selected = tuple(islice(books, MAX_BOOKS))
    if not selected:
        return []
    semaphore = asyncio.Semaphore(fanout)

    async def one(book_num: int) -> list[Chunk]:
        async with semaphore:
            return await retriever.retrieve_book(query, book_num, per_book_k)

    groups = await asyncio.gather(
        *(one(book_num) for book_num in selected), return_exceptions=True
    )
    by_id: dict[str, Chunk] = {}
    for book_num, group in zip(selected, groups, strict=True):
        if isinstance(group, BaseException):
            logger.warning("per-book retrieval failed for book %d: %s", book_num, group)
            continue
        for chunk in group:
            current = by_id.get(chunk.id)
            if current is None or chunk.score > current.score:
                by_id[chunk.id] = chunk
    return sorted(by_id.values(), key=lambda chunk: chunk.score, reverse=True)
