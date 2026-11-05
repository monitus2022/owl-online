"""Measure top rerank scores on the answerable and unanswerable gold slices.

Only the first retrieved chunk matters: ask() abstains when it scores below the
configured floor. Prints distributions and the false-abstention cost of
candidate floors so #23 can be pinned with evidence rather than a guess.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from eval.harness import load_gold  # noqa: E402

CANDIDATES = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)


async def measure(gold_path: Path, top_k: int) -> None:
    reranker = (
        None
        if settings.rerank_provider == "none"
        else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        REPO / "data/chunks.jsonl",
        REPO / "data/index/chroma",
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool,
        min_score=settings.rerank_min_score,
    )
    gold = load_gold(gold_path)
    answerable: list[float] = []
    unanswerable: list[float] = []
    for item in gold:
        chunks = await setup.retriever.retrieve(item.question, top_k)
        if not chunks:
            score = 0.0
        else:
            score = chunks[0].score
        (answerable if item.answerable else unanswerable).append(score)

    def summary(name: str, scores: list[float]) -> None:
        ordered = sorted(scores)
        print(
            f"{name}: n={len(ordered)} min={ordered[0]:.3f} "
            f"p10={ordered[len(ordered) // 10]:.3f} "
            f"median={statistics.median(ordered):.3f} "
            f"p90={ordered[(len(ordered) * 9) // 10]:.3f} "
            f"max={ordered[-1]:.3f}"
        )

    summary("answerable", answerable)
    summary("unanswerable", unanswerable)
    print()
    print("floor  false-abstain(answerable)  abstain(unanswerable)")
    for floor in CANDIDATES:
        false_abstain = sum(score < floor for score in answerable)
        covered = sum(score < floor for score in unanswerable)
        print(
            f"{floor:<5.1f}  {false_abstain:>3}/{len(answerable):<3}                 "
            f"{covered:>2}/{len(unanswerable)}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure the rerank floor")
    parser.add_argument(
        "--gold", type=Path, default=REPO / "eval" / "gold" / "questions.jsonl"
    )
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(measure(args.gold, args.k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
