# Testing providers/contracts.py
from fakes import FakeEmbedder, FakeLlm, FakeReranker, FakeRetriever

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
