"""Measure the aggregation fixture: per-book coverage, completeness and citations.

Run:
  uv run python scripts/measure_aggregation.py
  uv run python scripts/measure_aggregation.py --k 8
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.index.builder import load_chunks  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from eval.harness import (  # noqa: E402
    aggregation_metrics,
    entity_matches,
    load_aggregation,
)


def _verify_entities(items, chunks) -> list[str]:
    """Every expected entity must appear in its book; catch invented fixture facts."""
    by_book: dict[int, list[str]] = defaultdict(list)
    for chunk in chunks:
        by_book[chunk.metadata.book_num].append(chunk.text)
    missing: list[str] = []
    for item in items:
        for book in item.books:
            for entity in book.expected_entities:
                if not any(entity_matches(text, entity) for text in by_book[book.book_num]):
                    missing.append(f"{item.id} book {book.book_num}: {entity!r}")
    return missing


def _render(scores, metrics) -> str:
    lines = [
        "aggregation fixture",
        "item     kind        books covered entities found citations valid",
    ]
    for score in scores:
        lines.append(
            f"{score.item_id:8} {score.kind:11} "
            f"{score.expected_books:5} {score.covered_books:7} "
            f"{score.expected_entities:8} {score.found_entities:5} "
            f"{score.citations:9} {score.valid_citations:5}"
        )
    lines.extend(
        [
            "",
            "aggregate",
            f"  multi_book n={metrics.n_multi} book_coverage={metrics.book_coverage:.2f} "
            f"full_coverage={metrics.full_coverage_rate:.2f} "
            f"entity_completeness={metrics.entity_completeness:.2f}",
            f"  near_miss  n={metrics.n_near} entity_hit={metrics.near_miss_entity_hit:.2f} "
            f"book_precision={metrics.near_miss_book_precision:.2f}",
            f"  citation_validity={metrics.citation_validity:.2f}",
        ]
    )
    return "\n".join(lines)


async def run(args) -> int:
    items = load_aggregation(args.fixture)
    chunks = load_chunks(args.chunks)
    missing = _verify_entities(items, chunks)
    if missing:
        print("fixture entities missing from the corpus:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1

    reranker = (
        None if settings.rerank_provider == "none" else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        args.chunks,
        args.index,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
        subquery_quota=settings.subquery_quota,
    )
    try:
        scores, metrics = await aggregation_metrics(setup.retriever, items, args.k)
    finally:
        await setup.retriever.aclose()
    print(f"run: {args.run_id}")
    print(_render(scores, metrics))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the aggregation fixture")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "eval" / "fixtures" / "aggregation.jsonl",
    )
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--index", type=Path, default=REPO / "data" / "index" / "chroma"
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--run-id",
        default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
