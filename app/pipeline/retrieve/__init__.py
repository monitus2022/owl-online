"""Retrieval: dense, sparse, hybrid (RRF)."""

from app.pipeline.retrieve.composition import RetrievalSetup, compose_retriever
from app.pipeline.retrieve.multibook import (
    DEFAULT_FANOUT,
    MAX_BOOKS,
    BookRetriever,
    retrieve_multi_book,
)
from app.pipeline.retrieve.retriever import HybridRetriever
from app.pipeline.retrieve.strategy import (
    RetrievalStrategy,
    classify_retrieval_strategy,
    explicit_book_numbers,
)

__all__ = [
    "DEFAULT_FANOUT",
    "MAX_BOOKS",
    "BookRetriever",
    "HybridRetriever",
    "RetrievalSetup",
    "RetrievalStrategy",
    "classify_retrieval_strategy",
    "compose_retriever",
    "explicit_book_numbers",
    "retrieve_multi_book",
]
