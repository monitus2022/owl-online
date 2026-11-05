"""Bedrock adapters: reranker, embedder (Titan) and Llm (Converse).

Only this module imports the AWS SDK. Rerank results are disk-cached by
(model, query, top_n, candidate ids) per AGENTS.md. The embedder is the vendor
path for cloud deploys, where the local Ollama daemon is not available. The Llm
uses Converse and ConverseStream so the same adapter serves open-weight and
Amazon models in-region.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
import time
from collections.abc import AsyncIterator
from concurrent.futures import TimeoutError as FutureTimeout
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

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "amazon.rerank-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_TIMEOUT = 120.0
_MAX_RETRIES = 5
_THROTTLE_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
}
DEFAULT_LLM_MODEL = "qwen.qwen3-32b-v1:0"
DEFAULT_LLM_MAX_TOKENS = 1024

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
        start = time.perf_counter()
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
        logger.debug(
            "rerank %s: %d docs in %.0fms",
            self._model,
            len(chunks),
            (time.perf_counter() - start) * 1000,
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
        start = time.perf_counter()
        response = self._client.invoke_model(
            modelId=self._model,
            body=json.dumps(
                {"inputText": text, "dimensions": self._dimensions, "normalize": True}
            ),
        )
        logger.debug(
            "embed %s in %.0fms", self._model, (time.perf_counter() - start) * 1000
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
            if not isinstance(record, dict) or "key" not in record or "ranking" not in record:
                continue  # a well-formed line with the wrong shape must not raise
            cache[record["key"]] = record["ranking"]
    return cache


def _normalize(exc: BotoCoreError | ClientError) -> ProviderError:
    """Map a botocore error onto our types, keeping the cause for the traceback."""
    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError)):
        return ProviderTimeout(str(exc))
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        if code in _THROTTLE_CODES or code == "ModelNotReadyException":
            return ProviderRateLimited(str(exc))
        if code == "ModelTimeoutException":
            return ProviderTimeout(str(exc))
    return ProviderError(str(exc))


def _append_cache(path: Path | None, key: str, ranking: list[dict[str, Any]]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"key": key, "ranking": ranking}) + "\n")


class BedrockLlm:
    """Llm contract over Bedrock's Converse API.

    Converse is model-agnostic, so the same adapter serves open-weight Qwen,
    Llama, Mistral, and Amazon Nova in-region. Streaming runs the synchronous
    boto3 event stream in one worker thread and forwards deltas to the event
    loop through a queue.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_LLM_MODEL,
        region: str = DEFAULT_REGION,
        client: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        temperature: float | None = None,
        max_tokens: int = DEFAULT_LLM_MAX_TOKENS,
    ) -> None:
        self.name = f"bedrock/{model}"  # manifest pin + logging
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(read_timeout=timeout, retries={"max_attempts": _MAX_RETRIES}),
        )

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        context: str | None = None,
    ) -> str:
        start = time.perf_counter()
        try:
            response = await asyncio.to_thread(
                self._client.converse,
                **self._request(system, prompt, context),
            )
        except (BotoCoreError, ClientError) as exc:
            raise _normalize(exc) from exc
        logger.debug(
            "generate %s in %.0fms",
            self._model,
            (time.perf_counter() - start) * 1000,
        )
        if response.get("stopReason") == "max_tokens":
            logger.warning("bedrock %s hit max_tokens=%d", self._model, self._max_tokens)
        return _response_text(response)

    def stream(
        self,
        system: str,
        prompt: str,
        *,
        context: str | None = None,
    ) -> AsyncIterator[str]:
        return self._stream(system, prompt, context)

    async def _stream(
        self, system: str, prompt: str, context: str | None
    ) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=64)
        done = object()
        stop = threading.Event()
        stream_holder: list[Any] = []

        def put(item: Any) -> bool:
            """Put one item with bounded backpressure; return False when stopped."""
            if stop.is_set():
                return False
            try:
                future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
            except RuntimeError:  # loop already closed during shutdown
                return False
            while True:
                try:
                    future.result(timeout=0.5)
                    return True
                except FutureTimeout:
                    if stop.is_set():
                        future.cancel()
                        return False
                except Exception:
                    return False

        def worker() -> None:
            stream: Any | None = None
            try:
                if stop.is_set():
                    return
                response = self._client.converse_stream(
                    **self._request(system, prompt, context)
                )
                stream = response["stream"]
                stream_holder.append(stream)
                if stop.is_set():
                    return
                for event in stream:
                    if stop.is_set():
                        break
                    delta = event.get("contentBlockDelta", {}).get("delta", {})
                    text = delta.get("text")
                    if text and not put(text):
                        break
            except (BotoCoreError, ClientError) as exc:
                put(exc)
            except Exception as exc:  # malformed event or client bug: do not hang
                put(ProviderError(str(exc)))
            finally:
                if stream is not None:
                    close = getattr(stream, "close", None)
                    if close is not None:
                        try:
                            close()
                        except Exception:
                            pass
                if not stop.is_set():
                    put(done)

        # A daemon thread keeps an aborted Bedrock stream from delaying process
        # exit. The generator still sets stop and closes the stream on disconnect.
        threading.Thread(target=worker, daemon=True, name="bedrock-stream").start()
        try:
            while True:
                item = await queue.get()
                if item is done:
                    return
                if isinstance(item, (BotoCoreError, ClientError)):
                    raise _normalize(item) from item
                if isinstance(item, ProviderError):
                    raise item
                if isinstance(item, Exception):
                    raise ProviderError(str(item)) from item
                yield item
        finally:
            # A client disconnect cancels this generator. Stop the worker and try
            # to close the stream so a blocked read can unwind.
            stop.set()
            if stream_holder:
                close = getattr(stream_holder[0], "close", None)
                if close is not None:
                    try:
                        close()
                    except Exception:
                        pass

    async def aclose(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            close()

    def _request(
        self, system: str, prompt: str, context: str | None
    ) -> dict[str, Any]:
        user = prompt if context is None else f"{context}\n\n{prompt}"
        inference: dict[str, Any] = {"maxTokens": self._max_tokens}
        if self._temperature is not None:
            inference["temperature"] = self._temperature
        request: dict[str, Any] = {
            "modelId": self._model,
            "messages": [{"role": "user", "content": [{"text": user}]}],
            "inferenceConfig": inference,
        }
        if system.strip():
            request["system"] = [{"text": system}]
        return request


def _response_text(response: dict[str, Any]) -> str:
    message = response.get("output", {}).get("message", {})
    return "".join(
        block.get("text", "")
        for block in message.get("content", [])
        if isinstance(block, dict)
    )
