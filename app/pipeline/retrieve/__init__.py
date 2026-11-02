"""Retrieval: dense, sparse, hybrid (RRF)."""

from app.pipeline.retrieve.composition import RetrievalSetup, compose_retriever
from app.pipeline.retrieve.retriever import HybridRetriever

__all__ = ["HybridRetriever", "RetrievalSetup", "compose_retriever"]