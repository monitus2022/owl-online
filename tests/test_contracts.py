# Testing providers/contracts.py
import pytest

from app.providers.factory import (
    PROVIDERS,
    make_embedder,
    make_llm,
    make_reranker,
    make_retriever,
)
from app.providers.fakes import FakeEmbedder, FakeLlm, FakeReranker, FakeRetriever
from app.schemas import Chunk, ChunkMetadata


async def test_fake_embedder_returns_one_vector_per_input():
    """Test that the fake embedder returns one vector per input"""
    embedder = FakeEmbedder()
    texts = ["hello world", "goodbye world"]
    vectors = await embedder.embed(texts)
    assert len(vectors) == len(texts)


async def test_fake_reranker_returns_chunks_from_topk():
    """Test that the fake reranker returns chunks from top_k"""
    reranker = FakeReranker()
    query = "hello world"
    chunks = [
        Chunk(
            id=str(i),
            text=f"Chunk {i}",
            metadata=ChunkMetadata(
                book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
            ),
        )
        for i in range(10)
    ]
    top_k = 3
    ranked_chunks = await reranker.rerank(query, chunks, top_k)
    assert len(ranked_chunks) <= top_k


async def test_retriever_return_chunks():
    """Test that the fake retriever returns chunks"""
    retriever = FakeRetriever()
    query = "hello world"
    top_k = 3
    chunks = await retriever.retrieve(query, top_k)
    assert len(chunks) <= top_k


async def test_llm_generate():
    """Test that the fake LLM generates a response"""
    llm = FakeLlm()
    response = await llm.generate("Hello", "World")
    assert response == "Hello World!"


async def test_llm_stream_yield_text_tokens():
    """Test that the fake LLM streams a response"""
    llm = FakeLlm()
    tokens = [t async for t in llm.stream("Hello World!", "")]
    assert "".join(tokens) == "Hello World!"


# --- Swappability: the Done-when evidence for ticket #1 ---
# Same call, same contract behavior, for every provider the factory knows.
# Adding a provider must not change these tests: parametrize picks it up.


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_embedder_contract_swappable(provider):
    """Factory-built embedder satisfies the Embedder contract for each provider."""
    embedder = make_embedder(provider, model="test")
    vectors = await embedder.embed(["hello"])
    assert len(vectors) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_llm_contract_swappable(provider):
    """Factory-built Llm satisfies the Llm contract for each provider."""
    llm = make_llm(provider, model="test")
    response = await llm.generate("system", "prompt")
    assert isinstance(response, str)
    tokens = [t async for t in llm.stream("system", "prompt")]
    assert all(isinstance(t, str) for t in tokens)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_reranker_contract_swappable(provider):
    """Factory-built Reranker satisfies the Reranker contract for each provider."""
    chunks = [
        Chunk(
            id=str(i),
            text=f"Chunk {i}",
            metadata=ChunkMetadata(
                book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
            ),
        )
        for i in range(5)
    ]
    reranker = make_reranker(provider, model="test")
    ranked = await reranker.rerank("query", chunks, top_k=2)
    assert len(ranked) <= 2
    assert all(isinstance(c, Chunk) for c in ranked)


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_retriever_contract_swappable(provider):
    """Factory-built Retriever satisfies the Retriever contract for each provider."""
    retriever = make_retriever(provider)
    chunks = await retriever.retrieve("query", top_k=3)
    assert all(isinstance(c, Chunk) for c in chunks)


@pytest.mark.parametrize(
    "factory",
    [make_embedder, make_llm, make_reranker],
)
async def test_factory_rejects_unknown_provider(factory):
    """An unknown provider name raises ValueError, never a silent wrong object."""
    with pytest.raises(ValueError):
        factory("not-a-provider", model="any")


async def test_retriever_factory_rejects_unknown_provider():
    """Retriever factory takes no model; unknown provider still raises ValueError."""
    with pytest.raises(ValueError):
        make_retriever("not-a-provider")
