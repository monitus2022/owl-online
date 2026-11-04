"""Bedrock adapters: reranker (amazon.rerank-v1:0) and embedder (Titan).

Only this module imports the AWS SDK. Rerank results are disk-cached by
(model, query, top_n, candidate ids) per AGENTS.md. The embedder is the vendor
path for cloud deploys, where the local Ollama daemon is not available.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from app.providers.errors import ProviderError, ProviderRateLimited, ProviderTimeout
from app.schemas import Chunk

DEFAULT_MODEL = "amazon.rerank-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_TIMEOUT = 120.0
_MAX_RETRIES = 5
_THROTTLE_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
}

DEFAULT_EMBED_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_EMBED_DIMS = 1024
_EMBED_CONCURRENCY = 8


class BedrockReranker:
    """Reranker contract over Bedrock's Rerank API (an Amazon model)."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        region: str = DEFAULT_REGION,
        client: Any | None = None,
        cache_path: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.name = f"bedrock/{model}"  # manifest pin + logging
        self._model = model
        self._model_arn = f"arn:aws:bedrock:{region}::foundation-model/{model}"
        self._client = client or boto3.client(
            "bedrock-agent-runtime",
            region_name=region,
            config=Config(read_timeout=timeout, retries={"max_attempts": _MAX_RETRIES}),
        )
        self._cache_path = cache_path
        self._cache = _load_cache(cache_path)

    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]:
        """Reorder chunks by relevance and set score to the relevance value."""
        if not chunks:
            return []
        key = _cache_key(self._model, query, top_k, chunks)
        ranking = self._cache.get(key)
        if ranking is None:
            try:
                # boto3 is synchronous; keep the event loop free while it runs.
                ranking = await asyncio.to_thread(self._call, query, chunks, top_k)
            except (BotoCoreError, ClientError) as exc:
                raise _normalize(exc) from exc
            self._cache[key] = ranking
            _append_cache(self._cache_path, key, ranking)
        by_id = {chunk.id: chunk for chunk in chunks}
        return [
            by_id[item["chunk_id"]].model_copy(update={"score": item["score"]})
            for item in ranking
            if item["chunk_id"] in by_id
        ]

    def _call(self, query: str, chunks: list[Chunk], top_k: int) -> list[dict[str, Any]]:
        response = self._client.rerank(
            queries=[{"type": "TEXT", "textQuery": {"text": query}}],
            sources=[
                {
                    "type": "INLINE",
                    "inlineDocumentSource": {
                        "type": "TEXT",
                        "textDocument": {"text": chunk.text},
                    },
                }
                for chunk in chunks
            ],
            rerankingConfiguration={
                "type": "BEDROCK_RERANKING_MODEL",
                "bedrockRerankingConfiguration": {
                    "modelConfiguration": {"modelArn": self._model_arn},
                    "numberOfResults": top_k,
                },
            },
        )
        return [
            {"chunk_id": chunks[item["index"]].id, "score": float(item["relevanceScore"])}
            for item in response["results"][:top_k]
        ]


class BedrockEmbedder:
    """Embedder contract over Bedrock's Amazon Titan text embeddings."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_EMBED_MODEL,
        region: str = DEFAULT_REGION,
        dimensions: int = DEFAULT_EMBED_DIMS,
        client: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        # Dims are part of the slug: the index slug guard must not reuse a
        # collection built with a different vector width.
        self.name = f"bedrock/{model}:{dimensions}"
        self._model = model
        self._dimensions = dimensions
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=timeout, retries={"max_attempts": _MAX_RETRIES}),
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch; Titan takes one text per call, so calls run bounded-concurrent."""
        semaphore = asyncio.Semaphore(_EMBED_CONCURRENCY)

        async def one(text: str) -> list[float]:
            async with semaphore:
                try:
                    return await asyncio.to_thread(self._embed_one, text)
                except (BotoCoreError, ClientError) as exc:
                    raise _normalize(exc) from exc

        return await asyncio.gather(*(one(text) for text in texts))

    def _embed_one(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=self._model,
            body=json.dumps(
                {"inputText": text, "dimensions": self._dimensions, "normalize": True}
            ),
        )
        payload = json.loads(response["body"].read())
        return payload["embedding"]


def _cache_key(model: str, query: str, top_n: int, chunks: list[Chunk]) -> str:
    # Include chunk text: same ids with changed text must not reuse stale scores.
    documents = "\x1f".join(f"{chunk.id}\x1e{chunk.text}" for chunk in chunks)
    raw = f"{model}|{query}|{top_n}|{documents}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_cache(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    cache: dict[str, list[dict[str, Any]]] = {}
    if path is not None and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip a truncated line rather than break all reranking
            cache[record["key"]] = record["ranking"]
    return cache


def _normalize(exc: BotoCoreError | ClientError) -> ProviderError:
    """Map a botocore error onto our types, keeping the cause for the traceback."""
    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError)):
        return ProviderTimeout(str(exc))
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _THROTTLE_CODES:
            return ProviderRateLimited(str(exc))
    return ProviderError(str(exc))


def _append_cache(path: Path | None, key: str, ranking: list[dict[str, Any]]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, "ranking": ranking}) + "\n")
