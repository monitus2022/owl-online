"""Bedrock reranker: amazon.rerank-v1:0 via the bedrock-agent-runtime Rerank API.

Only this module imports the AWS SDK. Results are disk-cached by
(model, query, top_n, candidate ids) per AGENTS.md.
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
