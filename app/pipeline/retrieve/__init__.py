"""Retrieval: dense, sparse, hybrid (RRF)."""

from app.pipeline.retrieve.composition import RetrievalSetup, compose_retriever
from app.pipeline.retrieve.retriever import HybridRetriever
from app.pipeline.retrieve.strategy import (
    RetrievalStrategy,
    classify_retrieval_strategy,
)

__all__ = [
    "HybridRetriever",
    "RetrievalSetup",
    "RetrievalStrategy",
    "classify_retrieval_strategy",
    "compose_retriever",
]
