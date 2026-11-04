"""Bedrock reranker tests: a fake client stands in for AWS, no network."""

import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from app.providers.bedrock import BedrockEmbedder, BedrockReranker
from app.providers.errors import ProviderError, ProviderRateLimited, ProviderTimeout
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


class _ErrorClient:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def rerank(self, **kwargs):
        raise self._error

    def invoke_model(self, **kwargs):
        raise self._error


class _FakeBody:
    def __init__(self, data: dict) -> None:
        self._data = data

    def read(self) -> bytes:
        return json.dumps(self._data).encode("utf-8")


class _FakeEmbedClient:
    """Returns an embedding of the requested width and records calls."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        dims = json.loads(kwargs["body"]).get("dimensions", 1024)
        return {"body": _FakeBody({"embedding": [0.5] * dims})}


async def test_throttling_is_normalized():
    error = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "Rerank")
    with pytest.raises(ProviderRateLimited):
        await _reranker(_ErrorClient(error)).rerank("q", _CHUNKS, top_k=2)


async def test_connection_error_is_normalized_to_timeout():
    error = EndpointConnectionError(endpoint_url="https://bedrock")
    with pytest.raises(ProviderTimeout):
        await _reranker(_ErrorClient(error)).rerank("q", _CHUNKS, top_k=2)


async def test_other_client_error_is_normalized():
    error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Rerank")
    with pytest.raises(ProviderError):
        await _reranker(_ErrorClient(error)).rerank("q", _CHUNKS, top_k=2)


async def test_cache_skips_a_truncated_line(tmp_path):
    cache_path = tmp_path / "cache.jsonl"
    cache_path.write_text('{"key": "x", "ranking": [\n{"key": "y", "ranking": []}\n')
    reranker = _reranker(_FakeClient(), cache_path)
    assert "y" in reranker._cache  # valid line loaded, truncated line skipped


def _embedder(client, dimensions: int = 1024) -> BedrockEmbedder:
    return BedrockEmbedder(
        model="amazon.titan-embed-text-v2:0",
        region="us-east-1",
        dimensions=dimensions,
        client=client,
    )


async def test_embedder_returns_one_vector_per_input():
    vectors = await _embedder(_FakeEmbedClient()).embed(["a", "b"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024


async def test_embedder_request_body_and_dims():
    client = _FakeEmbedClient()
    await _embedder(client, dimensions=512).embed(["hello"])
    assert json.loads(client.calls[0]["body"]) == {
        "inputText": "hello",
        "dimensions": 512,
        "normalize": True,
    }


def test_embedder_name_includes_dims():
    assert _embedder(_FakeEmbedClient(), dimensions=512).name == (
        "bedrock/amazon.titan-embed-text-v2:0:512"
    )


async def test_embedder_error_is_normalized():
    error = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow"}}, "InvokeModel"
    )
    with pytest.raises(ProviderRateLimited):
        await _embedder(_ErrorClient(error)).embed(["x"])
