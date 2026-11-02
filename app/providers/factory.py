"""Provider factory: the single place a provider name becomes an object.

Called once at composition time (startup), never per request and never on
user input. The pipeline and agent receive contract objects, they never see
a provider name.
"""

from app.providers.contracts import Embedder, Llm, Reranker, Retriever
from app.providers.fakes import FakeEmbedder, FakeLlm, FakeReranker, FakeRetriever
from app.providers.local import OllamaEmbedder

# All provider names the factory accepts ("local" builds a real embedder).
PROVIDERS = ("bedrock", "openrouter", "local")
# The subset that hosts an Llm / Reranker — "local" has no hosted models.
MODEL_PROVIDERS = ("bedrock", "openrouter")


def make_embedder(provider: str, *, model: str | None = None) -> Embedder:
    """Build an Embedder for a provider name"""
    match provider:
        case "local":
            return OllamaEmbedder() if model is None else OllamaEmbedder(model=model)
        case "bedrock" | "openrouter":
            return FakeEmbedder()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_llm(provider: str, *, model: str | None = None) -> Llm:
    """Build an Llm for a provider name"""
    match provider:
        case "bedrock" | "openrouter":
            return FakeLlm()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_reranker(provider: str, *, model: str | None = None) -> Reranker:
    """Build a Reranker for a provider name"""
    match provider:
        case "bedrock" | "openrouter":
            return FakeReranker()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_retriever(provider: str) -> Retriever:
    """Build a Retriever for a provider name (concrete impl in the pipeline).

    No model kwarg: retrieval is provider-internal (local vector store + BM25),
    not a model call. The concrete hybrid retriever lands in the pipeline tickets.
    """
    match provider:
        case "bedrock" | "openrouter":
            return FakeRetriever()
        case _:
            raise ValueError(f"unknown provider: {provider}")
