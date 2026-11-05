"""Abstention metrics: how often ask() refuses on unanswerable items."""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.generate import DEFAULT_MAX_RETRIES, DEFAULT_TOP_K, ask
from app.providers.contracts import Llm, Retriever
from eval.harness.gold import GoldItem


@dataclass(frozen=True)
class AbstentionMetrics:
    """How often ask() refused on the unanswerable gold items."""

    n: int
    refused: int

    @property
    def rate(self) -> float:
        return self.refused / self.n if self.n else 0.0


@dataclass(frozen=True)
class AbstentionScore:
    """Per-item abstention outcome, before aggregation."""

    item_id: str
    refused: bool


async def abstention_scores(
    retriever: Retriever,
    llm: Llm,
    items: list[GoldItem],
    top_k: int = DEFAULT_TOP_K,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> list[AbstentionScore]:
    """Run every unanswerable item through ask() once and record the refusal."""
    scores: list[AbstentionScore] = []
    for item in items:
        if item.answerable:
            continue
        result = await ask(
            item.question,
            retriever=retriever,
            llm=llm,
            top_k=top_k,
            max_retries=max_retries,
        )
        scores.append(AbstentionScore(item.id, result.abstained))
    return scores


def summarize_abstention(scores: list[AbstentionScore]) -> AbstentionMetrics:
    """Count refusals."""
    return AbstentionMetrics(len(scores), sum(score.refused for score in scores))


async def abstention_metrics_all(
    retriever: Retriever,
    llm: Llm,
    items: list[GoldItem],
    top_k: int = DEFAULT_TOP_K,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> tuple[AbstentionMetrics, dict[str, AbstentionMetrics]]:
    """Overall and per-slice abstention metrics from one ask() pass."""
    scores = await abstention_scores(retriever, llm, items, top_k, max_retries)
    by_id = {item.id: item for item in items}
    groups: dict[str, list[AbstentionScore]] = {}
    for score in scores:
        groups.setdefault(by_id[score.item_id].primary_slice, []).append(score)
    by_slice = {
        name: summarize_abstention(group) for name, group in sorted(groups.items())
    }
    return summarize_abstention(scores), by_slice


async def abstention_metrics(
    retriever: Retriever,
    llm: Llm,
    items: list[GoldItem],
    top_k: int = DEFAULT_TOP_K,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AbstentionMetrics:
    """Run the unanswerable items through ask() and count refusals."""
    overall, _ = await abstention_metrics_all(retriever, llm, items, top_k, max_retries)
    return overall


async def abstention_metrics_by_slice(
    retriever: Retriever,
    llm: Llm,
    items: list[GoldItem],
    top_k: int = DEFAULT_TOP_K,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, AbstentionMetrics]:
    """Abstention metrics per unanswerable slice, from one ask() pass."""
    _, by_slice = await abstention_metrics_all(
        retriever, llm, items, top_k, max_retries
    )
    return by_slice