"""Measure the aggregation fixture: per-book coverage, completeness and citations.

Run:
  uv run python scripts/measure_aggregation.py
  uv run python scripts/measure_aggregation.py --k 8
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.index.builder import load_chunks  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.pipeline.retrieve.strategy import classify_retrieval_strategy  # noqa: E402
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from eval.harness import (  # noqa: E402
    aggregation_metrics,
    load_aggregation,
    missing_entities,
)
from eval.results import load_manifest  # noqa: E402


def _render(scores, metrics) -> str:
    total_entities = sum(score.expected_entities for score in scores)
    lines = [
        f"expected entities: {total_entities}",
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
            f"entity_completeness={metrics.near_miss_entity_completeness:.2f} "
            f"book_precision={metrics.near_miss_book_precision:.2f}",
            f"  citation_validity={metrics.citation_validity:.2f}",
        ]
    )
    return "\n".join(lines)


async def run(args) -> int:
    items = load_aggregation(args.fixture)
    chunks = load_chunks(args.chunks)
    missing = missing_entities(items, chunks)
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
    manifest = load_manifest()
    embedder_key = "cloud" if settings.embedder_provider == "bedrock" else "local"
    print(f"run: {args.run_id}")
    print(
        f"manifest: generator={manifest['generator']['model']} "
        f"judge={manifest['judge']['model']} "
        f"reranker={manifest['reranker']['model']} pool={settings.rerank_pool} "
        f"embedder={manifest['embedder'][embedder_key]['model']} "
        f"chunking={manifest['chunking']['size']}/{manifest['chunking']['overlap']}/"
        f"{manifest['chunking']['min_size']} "
        f"top_k={args.k} rrf_k={manifest['retrieval']['rrf_k']} "
        f"quota={settings.subquery_quota}"
    )
    true_positive = false_positive = false_negative = 0
    for item in items:
        predicted = classify_retrieval_strategy(item.question).is_multi_book
        actual = item.kind == "multi_book"
        true_positive += predicted and actual
        false_positive += predicted and not actual
        false_negative += not predicted and actual
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0
    )
    print(
        f"router: precision={precision:.2f} recall={recall:.2f} "
        f"tp={true_positive} fp={false_positive} fn={false_negative}"
    )
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
