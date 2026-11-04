"""Composition: chunks on disk + embedder -> wired HybridRetriever.

One function for every caller that wires retrieval together — the build
script, the API startup, and the eval harness.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.pipeline.index import build_index, build_lexical_index, load_chunks
from app.pipeline.retrieve.retriever import QUERY_CANDIDATES, HybridRetriever
from app.providers.contracts import Embedder, Reranker
from app.schemas import Chunk


@dataclass(frozen=True)
class RetrievalSetup:
    """The wired retriever plus what it was built from; callers log or pin this."""

    retriever: HybridRetriever
    chunks: int
    embedder: str
    dims: int
    rebuilt: bool


async def compose_retriever(
    chunks_path: Path,
    index_dir: Path,
    embedder: Embedder,
    *,
    reranker: Reranker | None = None,
    pool: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> RetrievalSetup:
    """Load chunks, (re)build the vector index, attach BM25 and rerank, wire the retriever."""
    chunks: list[Chunk] = load_chunks(chunks_path)
    built = await build_index(chunks, index_dir, embedder, progress=progress)
    bm25, ids, by_id = build_lexical_index(chunks)
    retriever = HybridRetriever(
        embedder=embedder,
        collection=built.collection,
        bm25=bm25,
        chunk_ids=ids,
        chunks_by_id=by_id,
        reranker=reranker,
        pool=pool,
        # Retrieve a wide pool for the reranker to reorder down to top_k.
        candidates=pool if pool is not None else QUERY_CANDIDATES,
    )
    return RetrievalSetup(
        retriever=retriever,
        chunks=len(chunks),
        embedder=built.collection.metadata.get("embedder", embedder.name),
        dims=built.dims,
        rebuilt=built.rebuilt,
    )
