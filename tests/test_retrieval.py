"""Hybrid retrieval tests: a real local index on a tiny fixture + fusion math."""

import asyncio

import pytest

from app.pipeline.index import build_index, build_lexical_index
from app.pipeline.retrieve import HybridRetriever, compose_retriever
from app.providers.factory import make_embedder
from app.providers.fakes import FakeEmbedder
from app.schemas import Chunk, ChunkMetadata


def _chunk(num: int, title: str, text: str) -> Chunk:
    return Chunk(
        id=f"b1-c{num:02d}-0000",
        text=text,
        metadata=ChunkMetadata(
            book_num=1, chapter_num=num, book_name="Invented Volume One", chapter_name=title
        ),
    )


# Invented sample content: distinct topics so dense and sparse behave visibly.
_CHUNKS = [
    _chunk(1, "BROOM SPORTS", "Quidditch is a fast flying sport played on broomsticks."),
    _chunk(2, "POTIONS CLASS", "Potions lessons brew shrinking solution herbs."),
    _chunk(3, "OWL POST", "Letters and parcels arrive by owl post at breakfast."),
    _chunk(4, "DARK FOREST", "Students stay out of the shadowy forest at night."),
    _chunk(5, "SORTING FEAST", "The sorting hat places new students into a house."),
    _chunk(6, "QUIET EVENING", "The common room falls quiet as the fire burns low."),
    _chunk(7, "SAMPLE END", "A short filler passage ends the sample corpus."),
]


@pytest.fixture(scope="session")
def index_parts(tmp_path_factory, ollama_running):
    """Real local index over the fixture, built once (Ollama must be running)."""
    if not ollama_running:
        pytest.skip("Ollama daemon not running")
    index_dir = tmp_path_factory.mktemp("index")
    built = asyncio.run(build_index(_CHUNKS, index_dir, make_embedder("local")))
    collection = built.collection
    bm25, ids, by_id = build_lexical_index(_CHUNKS)
    return collection, bm25, ids, by_id


def _retriever_for(index_parts) -> HybridRetriever:
    """Fresh embedder per test: its httpx pool must bind to the test's own loop."""
    collection, bm25, ids, by_id = index_parts
    return HybridRetriever(
        embedder=make_embedder("local"),
        collection=collection,
        bm25=bm25,
        chunk_ids=ids,
        chunks_by_id=by_id,
    )


async def test_retrieve_returns_valid_hit_list(index_parts):
    """Retriever contract shape: valid, unique, score-sorted chunks."""
    retriever = _retriever_for(index_parts)
    chunks = await retriever.retrieve("a fast flying sport on broomsticks", top_k=3)
    assert len(chunks) == 3
    assert all(isinstance(c, Chunk) for c in chunks)
    assert len({c.id for c in chunks}) == 3
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True)


async def test_topic_question_finds_the_right_chunk(index_parts):
    """The known-play-fixture question surfaces the quidditch chunk."""
    retriever = _retriever_for(index_parts)
    chunks = await retriever.retrieve("playing a sport on a flying broomstick", top_k=3)
    assert "b1-c01-0000" in [c.id for c in chunks]
    assert chunks[0].score > 0


async def test_compose_retriever_from_disk(tmp_path, ollama_running):
    """The composition function wires a retriever straight from a chunks file."""
    if not ollama_running:
        pytest.skip("Ollama daemon not running")
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        "\n".join(c.model_dump_json() for c in _CHUNKS[:3]) + "\n", encoding="utf-8"
    )
    index_dir = tmp_path / "index"

    setup = await compose_retriever(chunks_path, index_dir, make_embedder("local"))
    assert setup.chunks == 3
    assert setup.embedder == "ollama/qwen3-embedding:0.6b"
    assert setup.dims > 0
    assert setup.rebuilt is True
    hits = await setup.retriever.retrieve("quidditch", top_k=1)
    assert hits[0].id == "b1-c01-0000"

    # Slug guard via composition: same file, same embedder -> reuse, no rebuild.
    again = await compose_retriever(chunks_path, index_dir, make_embedder("local"))
    assert again.rebuilt is False


async def test_build_index_slug_guard_offline(tmp_path):
    """Slug change on the same dir forces a rebuild; matching slug reuses (offline)."""
    first = await build_index(_CHUNKS[:3], tmp_path, FakeEmbedder(name="fake/one"))
    assert first.rebuilt is True
    assert first.collection.metadata["embedder"] == "fake/one"
    assert first.dims == 100

    # Same dir, different slug: the guard must rebuild, not reuse stale vectors.
    second = await build_index(_CHUNKS[:3], tmp_path, FakeEmbedder(name="fake/two"))
    assert second.rebuilt is True
    assert second.collection.metadata["embedder"] == "fake/two"

    # Same dir, same slug and count: reuse, no re-embedding.
    third = await build_index(_CHUNKS[:3], tmp_path, FakeEmbedder(name="fake/two"))
    assert third.rebuilt is False


class _StubCollection:
    """Dense run stub: fixed id order, whatever candidate count is asked."""

    def __init__(self, ids):
        self._ids = ids

    def count(self):
        return len(self._ids)

    def query(self, *, query_embeddings, n_results):
        return {"ids": [self._ids[:n_results]]}


class _StubBM25:
    """Sparse run stub: one fixed score vector aligned to _CHUNKS order."""

    def __init__(self, scores):
        self._scores = scores

    def get_scores(self, tokens):
        return self._scores


async def test_rrf_prefers_multi_leg_hits():
    """A candidate found by both legs outranks single-leg hits; RRF math pinned."""
    chunks_by_id = {c.id: c for c in _CHUNKS}
    stub_retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000", "b1-c02-0000", "b1-c03-0000"]),
        bm25=_StubBM25([0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id=chunks_by_id,
    )
    hits = await stub_retriever.retrieve("anything", top_k=3)
    assert [c.id for c in hits] == ["b1-c02-0000", "b1-c01-0000", "b1-c03-0000"]
    expected = 1.0 / 61 + 1.0 / 62  # dense rank 2 + sparse rank 1, rrf_k=60
    assert abs(hits[0].score - expected) < 1e-9


class _StubReranker:
    """Records the pool it was handed and reverses it, stamping a score."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], int]] = []

    async def rerank(self, query, chunks, top_k):
        self.calls.append((query, [c.id for c in chunks], top_k))
        picked = list(reversed(chunks))[:top_k]
        return [c.model_copy(update={"score": 1.0}) for c in picked]


async def test_reranker_reorders_the_pool_and_replaces_the_floor():
    """With a reranker attached, retrieve reranks the pool and the floor switches."""
    chunks_by_id = {c.id: c for c in _CHUNKS}
    reranker = _StubReranker()
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000", "b1-c02-0000", "b1-c03-0000"]),
        bm25=_StubBM25([5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id=chunks_by_id,
        reranker=reranker,
        pool=3,
        candidates=3,
    )
    hits = await retriever.retrieve("anything", top_k=2)
    assert len(reranker.calls) == 1
    assert reranker.calls[0][2] == 2  # top_k passed through to the reranker
    assert [c.id for c in hits] == ["b1-c03-0000", "b1-c02-0000"]
    assert retriever.min_score == 0.0  # rerank relevance floor, not the RRF floor


async def test_reranker_respects_a_configured_relevance_floor():
    chunks_by_id = {c.id: c for c in _CHUNKS}
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000"]),
        bm25=_StubBM25([5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id=chunks_by_id,
        reranker=_StubReranker(),
        pool=3,
        candidates=3,
        rerank_min_score=0.3,
    )
    assert retriever.min_score == 0.3


async def test_reranker_abstains_when_the_top_hit_is_one_leg():
    """A one-leg top hit is below the two-leg floor, so nothing reaches the reranker."""
    chunks_by_id = {c.id: c for c in _CHUNKS}
    reranker = _StubReranker()
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000"]),
        bm25=_StubBM25([0.0] * len(_CHUNKS)),  # sparse finds nothing -> one-leg only
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id=chunks_by_id,
        reranker=reranker,
        pool=3,
        candidates=3,
    )
    assert await retriever.retrieve("anything", top_k=2) == []
    assert reranker.calls == []


async def test_pool_of_fifty_reaches_the_reranker():
    many = [_chunk(i, f"T{i}", f"text {i}") for i in range(60)]
    reranker = _StubReranker()
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection([c.id for c in many]),
        bm25=_StubBM25([1.0] * 60),
        chunk_ids=[c.id for c in many],
        chunks_by_id={c.id: c for c in many},
        reranker=reranker,
        pool=50,
        candidates=50,
    )
    await retriever.retrieve("q", top_k=5)
    assert len(reranker.calls[0][1]) == 50
