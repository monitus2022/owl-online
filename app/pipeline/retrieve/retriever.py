"""Hybrid retrieval: dense (Chroma) + sparse (BM25) runs fused with RRF.

Implements the Retriever contract. top_k is a call parameter; rrf_k and the
candidate pool size are manifest values in D7 (#53) with defaults here.
"""

from typing import Any, Protocol

from rank_bm25 import BM25Okapi

from app.pipeline.index import tokenize
from app.providers.contracts import Embedder, Reranker
from app.schemas import Chunk

DEFAULT_RRF_K = 60
QUERY_CANDIDATES = 20


class _VectorStore(Protocol):
    """The slice of a vector store the dense leg uses; stubs stay duck-typed."""

    def count(self) -> int: ...
    def query(self, *, query_embeddings: Any, n_results: int) -> Any: ...


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
        dense_ids = await self._dense_run(query)
        sparse_ids = self._sparse_run(query)
        fused = self._fuse(dense_ids, sparse_ids)
        ranked = [
            self._chunks_by_id[cid].model_copy(update={"score": score})
            for cid, score in fused
        ]
        if self._reranker is None:
            return ranked[:top_k]
        # Secondary lexical gate: a top hit reached by one leg only means the
        # corpus does not lexically cover the question, so abstain (return none)
        # rather than hand the reranker noise. This keeps abstention working when
        # a reranker is attached.
        if not ranked or ranked[0].score < self._two_leg_floor:
            return []
        return await self._reranker.rerank(query, ranked[: self._pool], top_k)

    async def _dense_run(self, query: str) -> list[str]:
        """Query the Chroma collection for the top candidates by embedding similarity."""
        n_results = min(self._candidates, self._collection.count())
        vectors = await self._embedder.embed([query])
        # Query-time dims guard: a wrong-model query against an existing index
        # must fail loudly rather than return neighbors in a foreign vector space.
        recorded = (getattr(self._collection, "metadata", None) or {}).get("dims")
        if recorded and len(vectors[0]) != recorded:
            raise ValueError(
                f"embedder returned {len(vectors[0])} dims; index was built with {recorded}"
            )
        result = self._collection.query(query_embeddings=vectors, n_results=n_results)
        return result["ids"][0]

    def _sparse_run(self, query: str) -> list[str]:
        """Query the BM25 index for the top candidates by token overlap."""
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
        return [self._chunk_ids[i] for i in order[: self._candidates] if scores[i] > 0]

    def _fuse(self, dense_ids: list[str], sparse_ids: list[str]) -> list[tuple[str, float]]:
        """RRF: each leg contributes 1/(rrf_k + rank), hits on both legs win."""
        fused: dict[str, float] = {}
        for ids in (dense_ids, sparse_ids):
            for rank, cid in enumerate(ids, start=1):
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (self._rrf_k + rank)
        return sorted(fused.items(), key=lambda item: item[1], reverse=True)
