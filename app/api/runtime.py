"""Composition root: build the contract objects once, at app startup.

The API receives wired contracts and never builds a provider per request.
"""

from dataclasses import dataclass

from app.config import Settings
from app.pipeline.retrieve import compose_retriever
from app.providers.contracts import Llm, Retriever
from app.providers.factory import make_embedder, make_llm


@dataclass(frozen=True)
class Runtime:
    """Wired contracts the API serves requests with."""

    retriever: Retriever
    llm: Llm


async def build_runtime(settings: Settings) -> Runtime:
    """Load the local hybrid index and build the configured model adapters."""
    setup = await compose_retriever(
        settings.chunks_path,
        settings.index_dir,
        make_embedder("local"),
    )
    return Runtime(retriever=setup.retriever, llm=make_llm(settings.provider))
