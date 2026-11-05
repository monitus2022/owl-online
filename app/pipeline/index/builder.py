"""Index building: chunks JSONL -> persisted Chroma vectors + in-process BM25.

chromadb here is storage, not a model call. Embedding is done by the Embedder
provider (slug pinned in the manifest, D7 #53). The collection records its
embedder slug so an index built with one model is never reused for queries
from another model's space.
"""

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

from app.providers.contracts import Embedder
from app.schemas import Chunk

COLLECTION_NAME = "owl-online"  # TODO: make this configurable, e.g. per corpus
EMBED_BATCH = 128  # Temporary batch size for embedding for now; public: callers derive cadence


@dataclass(frozen=True)
class BuiltIndex:
    """Result of one build_index call: the collection plus how it got there."""

    collection: chromadb.Collection
    rebuilt: bool
    dims: int
    text_hash: str


def load_chunks(path: Path) -> list[Chunk]:
    """Read the validated chunks JSONL back into Chunk objects."""
    return [
        Chunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def tokenize(text: str) -> list[str]:
    """Lowercased word tokens for BM25; punctuation-split."""
    return re.findall(r"[a-z0-9']+", text.lower())


def _metadata_of(chunk: Chunk) -> dict:
    m = chunk.metadata
    return {
        "book_num": m.book_num,
        "chapter_num": m.chapter_num,
        "book_name": m.book_name,
        "chapter_name": m.chapter_name,
    }


def _embedding_text(chunk: Chunk) -> str:
    """Text used for the dense and sparse index, but not for generation.

    A generated context is prepended when present; otherwise the original chunk
    is indexed unchanged.
    """
    context = chunk.context.strip()
    return f"{context}\n\n{chunk.text}" if context else chunk.text


def _text_hash(chunks: list[Chunk]) -> str:
    """Hash of ids and indexed text, so a context change forces a rebuild."""
    payload = "\n".join(f"{c.id}\t{_embedding_text(c)}" for c in chunks)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _add_batch(collection, batch: list[Chunk], embeddings: list[list[float]]) -> None:
    collection.add(
        ids=[c.id for c in batch],
        embeddings=embeddings,
        documents=[c.text for c in batch],
        metadatas=[_metadata_of(c) for c in batch],
    )


def _matching_collection(
    client, n_chunks: int, embedder_name: str, text_hash: str
) -> chromadb.Collection | None:
    """Reuse the persisted collection only when count, embedder and text match."""
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:  # chroma raises when the collection does not exist yet
        return None
    meta = collection.metadata or {}
    if (
        collection.count() == n_chunks
        and meta.get("embedder") == embedder_name
        and meta.get("text_hash") == text_hash
    ):
        return collection
    return None


async def embed_in_batches(chunks: list[Chunk], embedder: Embedder, *, batch_size=EMBED_BATCH):
    """Embed chunks in batches and yield (batch, embeddings) for callers to stream progress."""
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        embeddings = await embedder.embed([_embedding_text(c) for c in batch])
        yield batch, embeddings


async def build_index(
    chunks: list[Chunk],
    out_dir: Path,
    embedder: Embedder,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> BuiltIndex:
    """Embed all chunks into a persisted Chroma collection; rebuilds when stale."""
    if not chunks:
        raise ValueError("cannot build an index from zero chunks")
    client = chromadb.PersistentClient(path=str(out_dir))
    text_hash = _text_hash(chunks)
    current = _matching_collection(client, len(chunks), embedder.name, text_hash)
    if current is not None:
        meta = current.metadata or {}
        return BuiltIndex(
            collection=current,
            rebuilt=False,
            dims=meta.get("dims", 0),
            text_hash=meta.get("text_hash", text_hash),
        )

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:  # first build (or stale embedder): nothing to keep
        pass

    collection = None
    total, done = len(chunks), 0

    # Stream the embedding in batches; the collection is created after the first
    # batch so its metadata records the real dims and embedder slug.
    async for batch, embeddings in embed_in_batches(chunks, embedder):
        if collection is None:
            collection = client.create_collection(
                COLLECTION_NAME,
                metadata={
                    "hnsw:space": "cosine",
                    "embedder": embedder.name,
                    "dims": len(embeddings[0]),
                    "text_hash": text_hash,
                },
            )
        _add_batch(collection, batch, embeddings)
        done += len(batch)
        if progress is not None:
            progress(done, total)
    assert collection is not None  # chunks is non-empty, so at least one batch ran
    meta = collection.metadata or {}
    return BuiltIndex(
        collection=collection,
        rebuilt=True,
        dims=meta.get("dims", 0),
        text_hash=text_hash,
    )


def build_lexical_index(chunks: list[Chunk]) -> tuple[BM25Okapi, list[str], dict[str, Chunk]]:
    """BM25 over contextual text; ids and objects returned in corpus order."""
    ids = [c.id for c in chunks]
    bm25 = BM25Okapi([tokenize(_embedding_text(c)) for c in chunks])
    return bm25, ids, {c.id: c for c in chunks}
