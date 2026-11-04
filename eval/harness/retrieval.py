"""Retrieval metrics: Hit@k, Recall@k and MRR on chunk ids."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from app.pipeline.retrieve.retriever import RetrievalTrace
from app.providers.contracts import Retriever
from eval.harness.gold import GoldItem

_CHUNK_ID = re.compile(r"^b(\d+)-c(\d+)-(\d+)$")


class _DiagnosingRetriever(Protocol):
    async def diagnose(self, query: str, top_k: int) -> RetrievalTrace: ...


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


@dataclass(frozen=True)
class RetrievalDiagnostics:
    """Per-slice stage recall and rerank lift."""

    n: int
    dense_hit_n: int
    sparse_hit_n: int
    pool_hit_n: int
    result_hit_n: int
    neighbor_hit_n: int
    dense_recall_at_pool: float
    sparse_recall_at_pool: float
    pool_recall_at_pool: float
    rerank_lift: float
    rerank_loss: float
    neighbor_hit_rate: float


@dataclass(frozen=True)
class DiagnosticScore:
    """One item's stage outcome, before aggregation."""

    item_id: str
    slice_name: str
    dense_recall: float
    sparse_recall: float
    pool_recall: float
    pool_hit: bool
    result_hit: bool
    neighbor_hit: bool


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


def summarize_diagnostics(scores: list[DiagnosticScore]) -> RetrievalDiagnostics:
    """Average stage recall and rerank conversion over one group."""
    n = len(scores)
    if n == 0:
        return RetrievalDiagnostics(
            0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        )
    pool_hit_n = sum(score.pool_hit for score in scores)
    result_hit_n = sum(score.result_hit for score in scores)
    neighbor_hit_n = sum(score.neighbor_hit for score in scores)
    lift = result_hit_n / pool_hit_n if pool_hit_n else 0.0
    return RetrievalDiagnostics(
        n=n,
        dense_hit_n=sum(score.dense_recall > 0 for score in scores),
        sparse_hit_n=sum(score.sparse_recall > 0 for score in scores),
        pool_hit_n=pool_hit_n,
        result_hit_n=result_hit_n,
        neighbor_hit_n=neighbor_hit_n,
        dense_recall_at_pool=sum(score.dense_recall for score in scores) / n,
        sparse_recall_at_pool=sum(score.sparse_recall for score in scores) / n,
        pool_recall_at_pool=sum(score.pool_recall for score in scores) / n,
        rerank_lift=lift,
        rerank_loss=1.0 - lift if pool_hit_n else 0.0,
        neighbor_hit_rate=neighbor_hit_n / n,
    )


def _chunk_key(chunk_id: str) -> tuple[int, int, int] | None:
    match = _CHUNK_ID.match(chunk_id)
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def _neighbor_hit(expected: set[str], result_ids: tuple[str, ...]) -> bool:
    """True when a result is in the same book/chapter one chunk either side.

    This separates a genuine leg miss from a gold label that is too strict: the
    answer often spans the boundary between two chunks.
    """
    expected_keys = [key for cid in expected if (key := _chunk_key(cid)) is not None]
    for chunk_id in result_ids:
        key = _chunk_key(chunk_id)
        if key is None:
            continue
        for book, chapter, index in expected_keys:
            if key[0] == book and key[1] == chapter and abs(key[2] - index) <= 1:
                return True
    return False


async def retrieval_diagnostic_scores(
    retriever: _DiagnosingRetriever, items: list[GoldItem], k: int
) -> list[DiagnosticScore]:
    """Per-item stage recall: dense, sparse, fused pool and reranked result."""
    scores: list[DiagnosticScore] = []
    for item in items:
        if not item.answerable:
            continue
        trace = await retriever.diagnose(item.question, k)
        expected = set(item.expected_chunk_ids)
        if not expected:
            continue
        scores.append(
            DiagnosticScore(
                item_id=item.id,
                slice_name=item.primary_slice,
                dense_recall=len(expected & set(trace.dense_ids)) / len(expected),
                sparse_recall=len(expected & set(trace.sparse_ids)) / len(expected),
                pool_recall=len(expected & set(trace.pool_ids)) / len(expected),
                pool_hit=bool(expected & set(trace.pool_ids)),
                result_hit=bool(expected & set(trace.result_ids)),
                neighbor_hit=(
                    not bool(expected & set(trace.result_ids))
                    and _neighbor_hit(expected, trace.result_ids)
                ),
            )
        )
    return scores


async def retrieval_diagnostics_all(
    retriever: _DiagnosingRetriever, items: list[GoldItem], k: int
) -> tuple[RetrievalDiagnostics, dict[str, RetrievalDiagnostics]]:
    """Overall and per-slice stage diagnostics from one pass."""
    scores = await retrieval_diagnostic_scores(retriever, items, k)
    groups: dict[str, list[DiagnosticScore]] = {}
    for score in scores:
        groups.setdefault(score.slice_name, []).append(score)
    by_slice = {
        name: summarize_diagnostics(group) for name, group in sorted(groups.items())
    }
    return summarize_diagnostics(scores), by_slice


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