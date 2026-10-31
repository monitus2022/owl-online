from collections.abc import AsyncIterator
from typing import Protocol

from app.schemas import Chunk


class Llm(Protocol):
    """Vendor agnostic interface for LLMs"""

    async def generate(
        self,
        system: str,
        prompt: str,
        *,  # Accepts more keywords after this
        context: str | None = None,
    ) -> str: ...

    def stream(
        self,
        system: str,
        prompt: str,
        *,  # Accepts more keywords after this
        context: str | None = None,
    ) -> AsyncIterator[str]: ...


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class Reranker(Protocol):
    async def rerank(self, query: str, chunks: list[Chunk], top_k: int) -> list[Chunk]: ...


class Retriever(Protocol):
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]: ...
