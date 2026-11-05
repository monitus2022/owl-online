"""Composition root: build the contract objects once, at app startup.

The API receives wired contracts and never builds a provider per request.
"""

from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

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
    agent: CompiledStateGraph | None = None
    index_hash: str = "unknown-index"
    small_llm: Llm | None = None

    async def aclose(self) -> None:
        """Release provider clients on shutdown (embedder pool, model client)."""
        seen: set[int] = set()
        for component in (self.retriever, self.llm, self.small_llm):
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
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
    small_llm = (
        make_llm(settings.small_provider, model=settings.small_model)
        if settings.routing == "intent"
        else None
    )
    return Runtime(
        retriever=setup.retriever,
        llm=llm,
        index_hash=setup.text_hash,
        agent=build_graph(
            setup.retriever,
            llm,
            max_retries=settings.retry_budget,
            small_llm=small_llm,
        ),
        small_llm=small_llm,
    )
