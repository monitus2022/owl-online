"""Retrieval metrics: Hit@k, Recall@k and MRR on chunk ids."""

from __future__ import annotations

from dataclasses import dataclass

from app.providers.contracts import Retriever
from eval.harness.gold import GoldItem


@dataclass(frozen=True)
class RetrievalMetrics:
    """Hit@k, Recall@k and MRR over the answerable gold items."""

    n: int
    hit_at_k: float
    recall_at_k: float
    mrr: float


@dataclass(frozen=True)
class RetrievalScore:
    """Per-item retrieval outcome, before aggregation."""

    item_id: str
    hit: bool
    recall: float
    reciprocal_rank: float


async def retrieval_scores(
    retriever: Retriever, items: list[GoldItem], k: int
) -> list[RetrievalScore]:
    """Score every answerable item once: hit, recall and reciprocal rank."""
    scores: list[RetrievalScore] = []
    for item in items:
        if not item.answerable:
            continue
        retrieved = [chunk.id for chunk in await retriever.retrieve(item.question, k)]
        expected = set(item.expected_chunk_ids)
        found = expected.intersection(retrieved)
        recall = len(found) / len(expected) if expected else 0.0
        reciprocal = 0.0
        for rank, chunk_id in enumerate(retrieved, start=1):
            if chunk_id in expected:
                reciprocal = 1.0 / rank
                break
        scores.append(RetrievalScore(item.id, bool(found), recall, reciprocal))
    return scores


def summarize_retrieval(scores: list[RetrievalScore]) -> RetrievalMetrics:
    """Average the per-item retrieval scores."""
    n = len(scores)
    if n == 0:
        return RetrievalMetrics(0, 0.0, 0.0, 0.0)
    return RetrievalMetrics(
        n,
        sum(score.hit for score in scores) / n,
        sum(score.recall for score in scores) / n,
        sum(score.reciprocal_rank for score in scores) / n,
    )


async def retrieval_metrics_all(
    retriever: Retriever, items: list[GoldItem], k: int
) -> tuple[RetrievalMetrics, dict[str, RetrievalMetrics]]:
    """Overall and per-slice retrieval metrics from one retrieval pass."""
    scores = await retrieval_scores(retriever, items, k)
    by_id = {item.id: item for item in items}
    groups: dict[str, list[RetrievalScore]] = {}
    for score in scores:
        groups.setdefault(by_id[score.item_id].primary_slice, []).append(score)
    by_slice = {
        name: summarize_retrieval(group) for name, group in sorted(groups.items())
    }
    return summarize_retrieval(scores), by_slice


async def retrieval_metrics(
    retriever: Retriever, items: list[GoldItem], k: int
) -> RetrievalMetrics:
    """Score retrieval on chunk ids: hit if any expected id is in the top k."""
    overall, _ = await retrieval_metrics_all(retriever, items, k)
    return overall


async def retrieval_metrics_by_slice(
    retriever: Retriever, items: list[GoldItem], k: int
) -> dict[str, RetrievalMetrics]:
    """Retrieval metrics per answerable slice, from one retrieval pass."""
    _, by_slice = await retrieval_metrics_all(retriever, items, k)
    return by_slice