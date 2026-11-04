"""Bedrock reranker tests: a fake client stands in for AWS, no network."""

import json
from pathlib import Path

from app.providers.bedrock import BedrockReranker
from app.schemas import Chunk, ChunkMetadata


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
    )


_CHUNKS = [_chunk("c1", "alpha"), _chunk("c2", "beta"), _chunk("c3", "gamma")]


class _FakeClient:
    """Records calls; returns a fixed ranking that is not the input order."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def rerank(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "results": [
                {"index": 2, "relevanceScore": 0.9},
                {"index": 1, "relevanceScore": 0.4},
                {"index": 0, "relevanceScore": 0.1},
            ]
        }


def _reranker(client, cache_path: Path | None = None) -> BedrockReranker:
    return BedrockReranker(
        model="amazon.rerank-v1:0",
        region="us-east-1",
        client=client,
        cache_path=cache_path,
    )


async def test_rerank_orders_by_score_and_sets_relevance():
    client = _FakeClient()
    result = await _reranker(client).rerank("q", _CHUNKS, top_k=2)
    assert [c.id for c in result] == ["c3", "c2"]
    assert result[0].score == 0.9
    assert result[1].score == 0.4


async def test_rerank_builds_the_expected_request():
    client = _FakeClient()
    await _reranker(client).rerank("a question", _CHUNKS, top_k=2)
    call = client.calls[0]
    assert call["queries"] == [{"type": "TEXT", "textQuery": {"text": "a question"}}]
    assert [s["inlineDocumentSource"]["textDocument"]["text"] for s in call["sources"]] == [
        "alpha",
        "beta",
        "gamma",
    ]
    config = call["rerankingConfiguration"]["bedrockRerankingConfiguration"]
    assert config["modelConfiguration"]["modelArn"].endswith("amazon.rerank-v1:0")
    assert config["numberOfResults"] == 2


async def test_rerank_empty_pool_is_a_noop():
    client = _FakeClient()
    assert await _reranker(client).rerank("q", [], top_k=5) == []
    assert client.calls == []


async def test_rerank_is_cached_by_model_input(tmp_path):
    cache_path = tmp_path / "rerank_cache.jsonl"
    first_client = _FakeClient()
    await _reranker(first_client, cache_path).rerank("q", _CHUNKS, top_k=2)

    second_client = _FakeClient()
    result = await _reranker(second_client, cache_path).rerank("q", _CHUNKS, top_k=2)
    assert second_client.calls == []  # served from the on-disk cache
    assert [c.id for c in result] == ["c3", "c2"]
    assert json.loads(cache_path.read_text().splitlines()[0])["key"]


async def test_name_is_the_manifest_slug():
    assert _reranker(_FakeClient()).name == "bedrock/amazon.rerank-v1:0"
