"""Composition root: build the contract objects once, at app startup.

The API receives wired contracts and never builds a provider per request.
"""

from dataclasses import dataclass
from typing import Any

from app.agent import build_graph
from app.config import Settings
from app.pipeline.retrieve import compose_retriever
from app.providers.contracts import Llm, Retriever
from app.providers.factory import make_embedder, make_llm, make_reranker


@dataclass(frozen=True)
class Runtime:
    """Wired contracts the API serves requests with."""

    retriever: Retriever
    llm: Llm
    agent: Any = None

    async def aclose(self) -> None:
        """Release provider clients on shutdown (embedder pool, model client)."""
        for component in (self.retriever, self.llm):
            close = getattr(component, "aclose", None)
            if close is not None:
                await close()


async def build_runtime(settings: Settings) -> Runtime:
    """Load the local hybrid index and build the configured model adapters."""
    reranker = (
        None if settings.rerank_provider == "none" else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        settings.chunks_path,
        settings.index_dir,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
    )
    llm = make_llm(settings.provider)
    return Runtime(
        retriever=setup.retriever,
        llm=llm,
        agent=build_graph(setup.retriever, llm),
    )
