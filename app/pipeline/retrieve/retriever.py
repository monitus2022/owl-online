"""Hybrid retrieval: dense (Chroma) + sparse (BM25) runs fused with RRF.

Implements the Retriever contract. top_k is a call parameter; rrf_k and the
candidate pool size are manifest values in D7 (#53) with defaults here.
"""

from rank_bm25 import BM25Okapi

from app.pipeline.index import tokenize
from app.providers.contracts import Embedder
from app.schemas import Chunk

DEFAULT_RRF_K = 60
_QUERY_CANDIDATES = 20


class HybridRetriever:
    """Dense + sparse candidate lists joined by reciprocal rank fusion."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        collection: object,  # chromadb Collection, duck-typed for tests
        bm25: BM25Okapi,
        chunk_ids: list[str],
        chunks_by_id: dict[str, Chunk],
        rrf_k: int = DEFAULT_RRF_K,
        candidates: int = _QUERY_CANDIDATES,
    ) -> None:
        self._embedder = embedder
        self._collection = collection
        self._bm25 = bm25
        self._chunk_ids = chunk_ids
        self._chunks_by_id = chunks_by_id
        self._rrf_k = rrf_k
        self._candidates = candidates

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        """top_k chunks whose ids both legs can reach, ranked by fused score."""
        dense_ids = await self._dense_run(query)
        sparse_ids = self._sparse_run(query)
        fused = self._fuse(dense_ids, sparse_ids)
        return [
            self._chunks_by_id[cid].model_copy(update={"score": score})
            for cid, score in fused[:top_k]
        ]

    async def _dense_run(self, query: str) -> list[str]:
        """Query the Chroma collection for the top candidates by embedding similarity."""
        n_results = min(self._candidates, self._collection.count())
        vectors = await self._embedder.embed([query])
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