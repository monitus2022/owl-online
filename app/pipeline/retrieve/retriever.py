"""Hybrid retrieval: dense (Chroma) + sparse (BM25) runs fused with RRF.

Implements the Retriever contract. top_k is a call parameter; rrf_k and the
candidate pool size are manifest values in D7 (#53) with defaults here.
"""

import asyncio
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from rank_bm25 import BM25Okapi

from app.pipeline.index import tokenize
from app.pipeline.retrieve.decompose import split_question
from app.pipeline.retrieve.filters import MetadataFilter, parse_metadata_filter
from app.providers.contracts import Embedder, Reranker
from app.schemas import Chunk

logger = logging.getLogger(__name__)

DEFAULT_RRF_K = 60
QUERY_CANDIDATES = 20


@dataclass(frozen=True)
class RetrievalTrace:
    """Per-query ids at each stage, for eval diagnosis."""

    dense_ids: tuple[str, ...]
    sparse_ids: tuple[str, ...]
    pool_ids: tuple[str, ...]
    result_ids: tuple[str, ...]


def _unique(ids: Iterable[str]) -> list[str]:
    """Keep first-seen order while removing duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for chunk_id in ids:
        if chunk_id not in seen:
            seen.add(chunk_id)
            out.append(chunk_id)
    return out


def _combine_filter(
    part: MetadataFilter | None, base: MetadataFilter | None
) -> MetadataFilter | None:
    """Merge a sub-query filter with the original question's book context."""
    if part is None:
        return base
    if part.book_num is None and base is not None and base.book_num is not None:
        return MetadataFilter(base.book_num, part.chapter_num)
    return part


class _VectorStore(Protocol):
    """The slice of a vector store the dense leg uses; stubs stay duck-typed."""

    def count(self) -> int: ...
    def query(
        self, *, query_embeddings: Any, n_results: int, where: dict | None = None
    ) -> Any: ...


class HybridRetriever:
    """Dense + sparse candidate lists joined by reciprocal rank fusion."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        collection: _VectorStore,  # chromadb Collection, duck-typed for tests
        bm25: BM25Okapi,
        chunk_ids: list[str],
        chunks_by_id: dict[str, Chunk],
        rrf_k: int = DEFAULT_RRF_K,
        candidates: int = QUERY_CANDIDATES,
        reranker: Reranker | None = None,
        pool: int | None = None,
        rerank_min_score: float = 0.0,
        subquery_quota: int = 0,
    ) -> None:
        self._embedder = embedder
        self._collection = collection
        self._bm25 = bm25
        self._chunk_ids = chunk_ids
        self._chunks_by_id = chunks_by_id
        self._rrf_k = rrf_k
        self._candidates = candidates
        self._reranker = reranker
        self._pool = pool if pool is not None else candidates
        self._rerank_min_score = rerank_min_score
        self._subquery_quota = subquery_quota

    @property
    def _two_leg_floor(self) -> float:
        """Fused score a chunk must reach to be found by both retrieval legs."""
        return 2.0 / (self._rrf_k + self._candidates)

    @property
    def min_score(self) -> float:
        """Abstention floor: a rerank relevance floor, or the RRF two-leg score."""
        if self._reranker is not None:
            return self._rerank_min_score
        return self._two_leg_floor

    async def aclose(self) -> None:
        """Release the embedder's HTTP pool when the retriever is torn down."""
        close = getattr(self._embedder, "aclose", None)
        if close is not None:
            await close()

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        """top_k chunks: hybrid RRF, then reranked when a reranker is attached."""
        _, chunks = await self._run(query, top_k)
        return chunks

    async def diagnose(self, query: str, top_k: int) -> RetrievalTrace:
        """Run the same stages as retrieve and return the ids at each one."""
        trace, _ = await self._run(query, top_k)
        return trace

    async def _run(
        self, query: str, top_k: int
    ) -> tuple[RetrievalTrace, list[Chunk]]:
        """One retrieval pass, decomposed when the question asks two things."""
        sub_queries = split_question(query)
        decomposed = len(sub_queries) > 1
        # Keep the original question as an extra leg: it carries the context that
        # a bare sub-query loses, such as a pronoun in "who escapes from it?".
        retrieval_queries = sub_queries + ([query] if decomposed else [])
        base_filter = parse_metadata_filter(query)
        filters = [
            _combine_filter(parse_metadata_filter(part), base_filter)
            for part in retrieval_queries
        ]
        legs = await asyncio.gather(
            *(
                self._dense_run(part, spec)
                for part, spec in zip(retrieval_queries, filters, strict=True)
            ),
            *(
                self._sparse_run(part, spec)
                for part, spec in zip(retrieval_queries, filters, strict=True)
            ),
        )
        dense_lists = list(legs[: len(retrieval_queries)])
        sparse_lists = list(legs[len(retrieval_queries) :])
        filtered = any(spec is not None for spec in filters)
        explicit_filter = any(
            spec is not None and spec.explicit for spec in filters
        )
        if filtered and not any(dense_lists + sparse_lists):
            # The filtered pool would be empty: retry both legs unfiltered.
            legs = await asyncio.gather(
                *(self._dense_run(part, None) for part in retrieval_queries),
                *(self._sparse_run(part, None) for part in retrieval_queries),
            )
            dense_lists = list(legs[: len(retrieval_queries)])
            sparse_lists = list(legs[len(retrieval_queries) :])
            filtered = False
        dense_ids = _unique(cid for ids in dense_lists for cid in ids)
        sparse_ids = _unique(cid for ids in sparse_lists for cid in ids)
        if self._subquery_quota > 0 and decomposed:
            # Fuse each retrieval leg (sub-queries plus the original question)
            # and keep its top candidates, so one part of a two-part question
            # cannot crowd out the other.
            fused: list[tuple[str, float]] = []
            seen: set[str] = set()
            for part_dense, part_sparse in zip(
                dense_lists, sparse_lists, strict=True
            ):
                for cid, score in self._fuse_many([part_dense, part_sparse])[
                    : self._subquery_quota
                ]:
                    if cid not in seen:
                        seen.add(cid)
                        fused.append((cid, score))
            # The legs are concatenated sub-query-major; restore score order so
            # the no-reranker path and the trace see the best hit first.
            fused.sort(key=lambda item: item[1], reverse=True)
        else:
            fused = self._fuse_many(dense_lists + sparse_lists)
        ranked = [
            self._chunks_by_id[cid].model_copy(update={"score": score})
            for cid, score in fused
        ]
        pool_ids = tuple(cid for cid, _ in fused[: self._pool])
        # A parsed filter or a decomposed question is explicit evidence, so the
        # two-leg lexical floor is relaxed for those queries.
        floor = 0.0 if decomposed or explicit_filter else self._two_leg_floor
        if self._reranker is None:
            result = ranked[:top_k]
        elif not ranked or ranked[0].score < floor:
            result = []
        else:
            start = time.perf_counter()
            pool = ranked[: self._pool]
            # The reranker rejects numberOfResults larger than the source count,
            # which the sub-query quota can produce.
            result = await self._reranker.rerank(
                query, pool, min(top_k, len(pool))
            )
            logger.debug(
                "rerank: pool=%d -> %d in %.0fms",
                min(len(ranked), self._pool),
                len(result),
                (time.perf_counter() - start) * 1000,
            )
        trace = RetrievalTrace(
            dense_ids=tuple(dense_ids),
            sparse_ids=tuple(sparse_ids),
            pool_ids=pool_ids,
            result_ids=tuple(chunk.id for chunk in result),
        )
        return trace, result

    async def _dense_run(
        self, query: str, metadata_filter: MetadataFilter | None = None
    ) -> list[str]:
        """Query the Chroma collection for the top candidates by embedding similarity."""
        start = time.perf_counter()
        vectors = await self._embedder.embed([query])
        # Query-time dims guard: a wrong-model query against an existing index
        # must fail loudly rather than return neighbors in a foreign vector space.
        recorded = (getattr(self._collection, "metadata", None) or {}).get("dims")
        if recorded and len(vectors[0]) != recorded:
            raise ValueError(
                f"embedder returned {len(vectors[0])} dims; index was built with {recorded}"
            )
        # chromadb is synchronous; keep the sqlite query off the event loop.
        where = metadata_filter.chroma_where() if metadata_filter is not None else None
        result = await asyncio.to_thread(self._dense_query, vectors, where)
        ids = result["ids"][0]
        logger.debug(
            "dense: %d candidates in %.0fms", len(ids), (time.perf_counter() - start) * 1000
        )
        return ids

    def _dense_query(self, vectors: list[list[float]], where: dict | None = None) -> Any:
        """The blocking part of the dense leg: count + query the collection."""
        n_results = min(self._candidates, self._collection.count())
        query: dict[str, Any] = {
            "query_embeddings": vectors,
            "n_results": n_results,
        }
        if where is not None:
            query["where"] = where
        return self._collection.query(**query)

    async def _sparse_run(
        self, query: str, metadata_filter: MetadataFilter | None = None
    ) -> list[str]:
        """Query the BM25 index for the top candidates by token overlap."""
        # BM25 scoring over the whole corpus is CPU-bound; keep it off the loop.
        start = time.perf_counter()
        allowed = (
            self._allowed_ids(metadata_filter)
            if metadata_filter is not None
            else None
        )
        ids = await asyncio.to_thread(self._sparse_query, query, allowed)
        logger.debug(
            "sparse: %d candidates in %.0fms", len(ids), (time.perf_counter() - start) * 1000
        )
        return ids

    def _allowed_ids(self, metadata_filter: MetadataFilter) -> list[str]:
        """Chunk ids that match a parsed book/chapter filter."""
        return [
            chunk_id
            for chunk_id in self._chunk_ids
            if metadata_filter.matches(
                self._chunks_by_id[chunk_id].metadata.model_dump()
            )
        ]

    def _sparse_query(self, query: str, allowed_ids: list[str] | None = None) -> list[str]:
        """The blocking part of the sparse leg: score and rank the corpus or a subset."""
        scores = self._bm25.get_scores(tokenize(query))
        if allowed_ids is None:
            order = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
        else:
            allowed = set(allowed_ids)
            order = sorted(
                (i for i, cid in enumerate(self._chunk_ids) if cid in allowed),
                key=scores.__getitem__,
                reverse=True,
            )
        return [self._chunk_ids[i] for i in order[: self._candidates] if scores[i] > 0]

    def _fuse_many(
        self, lists: Iterable[list[str]]
    ) -> list[tuple[str, float]]:
        """RRF over one or more ranked lists; hits on more lists win."""
        fused: dict[str, float] = {}
        for ids in lists:
            for rank, cid in enumerate(ids, start=1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (self._rrf_k + rank)
        return sorted(fused.items(), key=lambda item: item[1], reverse=True)
