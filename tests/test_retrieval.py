"""Hybrid retrieval tests: a real local index on a tiny fixture + fusion math."""

import asyncio
import time

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


async def test_diagnose_returns_each_retrieval_stage(index_parts):
    retriever = _retriever_for(index_parts)
    query = "playing a sport on a flying broomstick"
    trace = await retriever.diagnose(query, top_k=3)
    chunks = await retriever.retrieve(query, top_k=3)
    assert trace.result_ids == tuple(chunk.id for chunk in chunks)
    assert trace.pool_ids
    assert trace.dense_ids
    assert trace.sparse_ids


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


async def test_build_index_text_change_forces_rebuild(tmp_path):
    first = await build_index(_CHUNKS[:3], tmp_path, FakeEmbedder(name="fake/one"))
    assert first.rebuilt is True
    changed = [
        chunk.model_copy(update={"text": f"{chunk.text} changed"})
        for chunk in _CHUNKS[:3]
    ]
    second = await build_index(changed, tmp_path, FakeEmbedder(name="fake/one"))
    assert second.rebuilt is True


async def test_build_index_context_change_forces_rebuild(tmp_path):
    first = await build_index(_CHUNKS[:3], tmp_path, FakeEmbedder(name="fake/one"))
    assert first.rebuilt is True
    changed = [
        chunk.model_copy(update={"context": "A generated retrieval context."})
        for chunk in _CHUNKS[:3]
    ]
    second = await build_index(changed, tmp_path, FakeEmbedder(name="fake/one"))
    assert second.rebuilt is True
    third = await build_index(changed, tmp_path, FakeEmbedder(name="fake/one"))
    assert third.rebuilt is False
    stored = third.collection.get(ids=[changed[0].id])
    assert stored["documents"][0] == changed[0].text


class _StubCollection:
    """Dense run stub: fixed id order, whatever candidate count is asked."""

    def __init__(self, ids):
        self._ids = ids

    def count(self):
        return len(self._ids)

    def query(self, *, query_embeddings, n_results, where=None):
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


class _RoutedEmbedder:
    """One-hot vectors that let the stub collection tell the legs apart."""

    def __init__(self, routes: dict[str, int]) -> None:
        self._routes = routes

    async def embed(self, texts):
        return [[float(self._routes.get(text, 0))] for text in texts]


class _RoutedCollection:
    """Dense stub that returns a different id list for each routed query."""

    def __init__(self, by_route: dict[int, list[str]], count: int) -> None:
        self._by_route = by_route
        self._count = count

    def count(self) -> int:
        return self._count

    def query(self, *, query_embeddings, n_results, where=None):
        route = int(query_embeddings[0][0])
        return {"ids": [self._by_route.get(route, [])[:n_results]]}


class _RoutedBM25:
    """Sparse stub keyed by a token that appears in only one sub-query."""

    def __init__(self, by_token: dict[str, list[float]]) -> None:
        self._by_token = by_token

    def get_scores(self, tokens):
        present = set(tokens)
        if "potions" in present:
            return self._by_token["potions"]
        return [0.0] * len(_CHUNKS)


_QUOTA_QUERY = "What is quidditch and what is potions?"
_QUOTA_ROUTES = {
    "What is quidditch?": 1,
    "what is potions?": 2,
    _QUOTA_QUERY: 3,
}
_QUOTA_DENSE = {
    1: ["b1-c01-0000", "b1-c03-0000", "b1-c04-0000"],
    2: ["b1-c05-0000"],
    3: ["b1-c02-0000"],
}
_QUOTA_SPARSE = {
    "potions": [0.0, 0.0, 0.0, 0.0, 5.0, 0.0, 0.0],
}


def _quota_retriever(*, quota: int, reranker=None, pool: int | None = None) -> HybridRetriever:
    return HybridRetriever(
        embedder=_RoutedEmbedder(_QUOTA_ROUTES),
        collection=_RoutedCollection(_QUOTA_DENSE, count=len(_CHUNKS)),
        bm25=_RoutedBM25(_QUOTA_SPARSE),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
        reranker=reranker,
        pool=pool,
        subquery_quota=quota,
    )


async def test_quota_keeps_a_candidate_from_each_leg():
    """Quota 1 keeps one fused hit per leg, dropping deeper dominant-leg hits."""
    retriever = _quota_retriever(quota=1)
    hits = await retriever.retrieve(_QUOTA_QUERY, top_k=4)
    assert [c.id for c in hits] == ["b1-c05-0000", "b1-c01-0000", "b1-c02-0000"]
    assert "b1-c03-0000" not in [c.id for c in hits]
    scores = [c.score for c in hits]
    assert scores == sorted(scores, reverse=True)


async def test_quota_zero_keeps_global_fusion():
    """Quota 0 still returns deeper hits from the dominant leg."""
    retriever = _quota_retriever(quota=0)
    hits = await retriever.retrieve(_QUOTA_QUERY, top_k=4)
    assert "b1-c03-0000" in [c.id for c in hits]


async def test_quota_trace_keeps_the_union_of_all_legs():
    """The trace must not be shadowed by the per-leg loop."""
    retriever = _quota_retriever(quota=1)
    trace = await retriever.diagnose(_QUOTA_QUERY, top_k=3)
    assert set(trace.dense_ids) == {
        "b1-c01-0000",
        "b1-c02-0000",
        "b1-c03-0000",
        "b1-c04-0000",
        "b1-c05-0000",
    }
    assert trace.sparse_ids == ("b1-c05-0000",)


class _FilterCollection:
    """Dense stub that honours a Chroma where clause and records it."""

    def __init__(self, filtered_ids, unfiltered_ids):
        self._filtered = filtered_ids
        self._unfiltered = unfiltered_ids
        self.wheres: list[dict | None] = []

    def count(self):
        return len(self._unfiltered)

    def query(self, *, query_embeddings, n_results, where=None):
        self.wheres.append(where)
        ids = self._filtered if where is not None else self._unfiltered
        return {"ids": [ids[:n_results]]}


async def test_metadata_filter_is_applied_to_both_legs():
    collection = _FilterCollection(["b1-c01-0000"], ["b1-c02-0000"])
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=collection,
        bm25=_StubBM25([5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
    )
    hits = await retriever.retrieve("In book 1, chapter 1, what happens?", top_k=1)
    assert collection.wheres == [{"$and": [{"book_num": {"$eq": 1}}, {"chapter_num": {"$eq": 1}}]}]
    assert hits[0].id == "b1-c01-0000"


async def test_empty_filtered_result_falls_back_to_unfiltered():
    collection = _FilterCollection([], ["b1-c02-0000"])
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=collection,
        bm25=_StubBM25([0.0] * len(_CHUNKS)),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
    )
    hits = await retriever.retrieve("In book 6, chapter 30, what happens?", top_k=1)
    assert collection.wheres[0] is not None
    assert collection.wheres[1] is None
    assert hits[0].id == "b1-c02-0000"


def test_sparse_query_restricts_to_allowed_ids():
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000"]),
        bm25=_StubBM25([1.0, 5.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
    )
    assert retriever._sparse_query("q", ["b1-c01-0000"]) == ["b1-c01-0000"]
    assert retriever._sparse_query("q")[0] == "b1-c02-0000"


def test_fuse_many_accumulates_three_lists():
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000"]),
        bm25=_StubBM25([0.0] * len(_CHUNKS)),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
    )
    fused = retriever._fuse_many(
        [["a", "b"], ["b", "c"], ["b", "a"]]
    )
    assert fused[0][0] == "b"
    assert fused[1][0] == "a"


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


async def test_reranker_request_is_capped_at_the_pool_size():
    """Bedrock rejects numberOfResults above the source count; cap it here."""
    reranker = _StubReranker()
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection(["b1-c01-0000"]),
        bm25=_StubBM25([5.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
        reranker=reranker,
        pool=1,
        candidates=1,
    )
    hits = await retriever.retrieve("anything", top_k=5)
    assert reranker.calls[0][2] == 1
    assert [c.id for c in hits] == ["b1-c01-0000"]


async def test_reranker_is_not_called_for_an_empty_pool():
    reranker = _StubReranker()
    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_StubCollection([]),
        bm25=_StubBM25([0.0] * len(_CHUNKS)),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
        reranker=reranker,
        pool=1,
        candidates=1,
    )
    assert await retriever.retrieve("anything", top_k=5) == []
    assert reranker.calls == []


async def test_retrieve_does_not_block_the_event_loop():
    """The sync Chroma query runs in a thread; the loop keeps ticking meanwhile."""
    ticks = 0

    class _SlowCollection:
        def count(self) -> int:
            return 1

        def query(self, *, query_embeddings, n_results):
            time.sleep(0.2)  # a blocking sqlite call that must not freeze the loop
            return {"ids": [["b1-c01-0000"]]}

    class _FlatBM25:
        def get_scores(self, tokens):
            return [1.0] * len(_CHUNKS)

    retriever = HybridRetriever(
        embedder=FakeEmbedder(),
        collection=_SlowCollection(),
        bm25=_FlatBM25(),
        chunk_ids=[c.id for c in _CHUNKS],
        chunks_by_id={c.id: c for c in _CHUNKS},
    )

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        await retriever.retrieve("q", top_k=1)
    finally:
        task.cancel()
    assert ticks >= 5  # the loop ran while the 0.2s blocking query was in a thread
