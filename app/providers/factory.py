"""Provider factory: the single place a provider name becomes an object.

Called once at composition time (startup), never per request and never on
user input. The pipeline and agent receive contract objects; they never see
a provider name.
"""

# TODO: replace with real providers once they land (ticket #36)

from app.providers.contracts import Embedder, Llm, Reranker, Retriever
from app.providers.fakes import FakeEmbedder, FakeLlm, FakeReranker, FakeRetriever

PROVIDERS = ("bedrock", "openrouter")


def make_embedder(provider: str, *, model: str = "unspecified") -> Embedder:
    """Build an Embedder for a provider name (fake until #36)."""
    match provider:
        case "bedrock" | "openrouter":
            return FakeEmbedder()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_llm(provider: str, *, model: str = "unspecified") -> Llm:
    """Build an Llm for a provider name (fake until #36)."""
    match provider:
        case "bedrock" | "openrouter":
            return FakeLlm()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_reranker(provider: str, *, model: str = "unspecified") -> Reranker:
    """Build a Reranker for a provider name (fake until #36)."""
    match provider:
        case "bedrock" | "openrouter":
            return FakeReranker()
        case _:
            raise ValueError(f"unknown provider: {provider}")


def make_retriever(provider: str) -> Retriever:
    """Build a Retriever for a provider name (concrete pipeline impl in M1).

    No model kwarg: retrieval is provider-internal (local vector store + BM25),
    not a model call. Concrete hybrid retriever lands in M1 pipeline tickets.
    """
    match provider:
        case "bedrock" | "openrouter":
            return FakeRetriever()
        case _:
            raise ValueError(f"unknown provider: {provider}")
