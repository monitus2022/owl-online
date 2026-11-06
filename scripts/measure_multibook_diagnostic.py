"""Retrieval-only diagnostic for the multi-book spike (#105).

No model generation. For every multi-book item and every expected book, this
retrieves the book's top candidates and reports where the first expected entity
appears and how the relevance scores are distributed.

Run:
  uv run python scripts/measure_multibook_diagnostic.py
  uv run python scripts/measure_multibook_diagnostic.py --per-book-k 15
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from eval.harness import entity_matches, load_aggregation  # noqa: E402
from eval.results import load_manifest  # noqa: E402

KS = (1, 3, 5, 7, 15)


def _percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _score_line(label: str, values: list[float]) -> str:
    return (
        f"  {label:28} n={len(values):3} "
        f"p10={_percentile(values, 0.10):.4f} "
        f"p50={_percentile(values, 0.50):.4f} "
        f"p90={_percentile(values, 0.90):.4f}"
    )


async def run(args) -> int:
    items = load_aggregation(args.fixture)
    multi = [item for item in items if item.kind == "multi_book"]
    if not multi:
        print("fixture has no multi_book items", file=sys.stderr)
        return 1

    reranker = (
        None
        if settings.rerank_provider == "none"
        else make_reranker(settings.rerank_provider)
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
    rows: list[dict[str, object]] = []
    try:
        for item in multi:
            for book in item.books:
                chunks = await setup.retriever.retrieve_book(
                    item.question, book.book_num, args.per_book_k
                )
                first_rank = None
                for rank, chunk in enumerate(chunks, 1):
                    if any(
                        entity_matches(chunk.text, entity)
                        for entity in book.expected_entities
                    ):
                        first_rank = rank
                        break
                rows.append(
                    {
                        "item_id": item.id,
                        "book_num": book.book_num,
                        "entities": list(book.expected_entities),
                        "returned": len(chunks),
                        "first_rank": first_rank,
                        "first_score": (
                            chunks[first_rank - 1].score
                            if first_rank is not None
                            else None
                        ),
                        "top_score": chunks[0].score if chunks else None,
                        "scores": [round(chunk.score, 6) for chunk in chunks],
                    }
                )
    finally:
        await setup.retriever.aclose()

    pairs = len(rows)
    hits = {
        k: sum(
            1
            for row in rows
            if row["first_rank"] is not None and int(row["first_rank"]) <= k
        )
        for k in KS
    }
    first_scores = [
        float(row["first_score"])
        for row in rows
        if row["first_score"] is not None
    ]
    top_scores = [
        float(row["top_score"]) for row in rows if row["top_score"] is not None
    ]
    ranks = [
        int(row["first_rank"])
        for row in rows
        if row["first_rank"] is not None
    ]
    missing = [row for row in rows if row["first_rank"] is None]

    manifest = load_manifest()
    embedder_key = "cloud" if settings.embedder_provider == "bedrock" else "local"
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    print(f"run: {run_id}")
    print(f"fixture: {args.fixture}")
    print(f"items: {len(multi)} multi_book, {pairs} (item, book) pairs")
    print(
        f"per_book_k={args.per_book_k} "
        f"reranker={manifest['reranker']['model']} pool={settings.rerank_pool} "
        f"embedder={manifest['embedder'][embedder_key]['model']} "
        f"top_k={args.per_book_k} rrf_k={manifest['retrieval']['rrf_k']}"
    )
    print()
    print("per-book hit rate (any expected entity in the top k)")
    for k in KS:
        rate = hits[k] / pairs if pairs else 0.0
        print(f"  k={k:<2} {rate:.2f} ({hits[k]}/{pairs})")
    print()
    print("score distribution")
    print(_score_line("first relevant chunk", first_scores))
    print(_score_line("top-1 chunk", top_scores))
    if ranks:
        print(
            f"  {'first relevant rank':28} n={len(ranks):3} "
            f"p50={_percentile([float(r) for r in ranks], 0.50):.0f} "
            f"p90={_percentile([float(r) for r in ranks], 0.90):.0f} "
            f"max={max(ranks)}"
        )
    print()
    print("per item")
    for row in rows:
        rank = row["first_rank"]
        first_score = row["first_score"]
        rank_text = "miss" if rank is None else str(rank)
        score_text = "n/a" if first_score is None else f"{float(first_score):.4f}"
        print(
            f"  {row['item_id']:8} b{int(row['book_num'])} "
            f"rank={rank_text:>4} score={score_text:>7} "
            f"entities={','.join(row['entities'])}"
        )
    if missing:
        print()
        print(f"missing in top {args.per_book_k}: {len(missing)}")
        for row in missing:
            print(
                f"  {row['item_id']} b{int(row['book_num'])} "
                f"entities={','.join(row['entities'])}"
            )

    args.results.mkdir(parents=True, exist_ok=True)
    out = args.results / f"{run_id}-multibook-diagnostic.json"
    out.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "fixture": str(args.fixture),
                "items": len(multi),
                "pairs": pairs,
                "per_book_k": args.per_book_k,
                "hits": hits,
                "first_scores": first_scores,
                "top_scores": top_scores,
                "ranks": ranks,
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print()
    print(f"wrote {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieval-only multi-book diagnostic"
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "eval" / "fixtures" / "aggregation.jsonl",
    )
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--index", type=Path, default=REPO / "data" / "index" / "chroma"
    )
    parser.add_argument("--per-book-k", type=int, default=15)
    parser.add_argument(
        "--results", type=Path, default=REPO / "eval" / ".cache"
    )
    parser.add_argument("--run-id", default=None)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
