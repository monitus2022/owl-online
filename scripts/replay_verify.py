"""Replay the judged sample through ask() and count verification retries.

The eval summary does not say whether a retry fired. This replays the same
questions with a cache-only generator and reports how many drafts deterministic
verification rejected. It makes no generation calls, but it does run retrieval,
so run it after an eval to reuse the warm embedding and rerank caches.

Run after an eval to back the run record:

  uv run python scripts/replay_verify.py

A cache miss means the replay is not comparable to the recorded run; rerun the
eval first in that case.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import settings  # noqa: E402
from app.pipeline.generate import ABSTAIN_MESSAGE, DEFAULT_TOP_K, ask  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_reranker  # noqa: E402
from app.providers.openrouter import DEFAULT_MODEL  # noqa: E402
from eval.harness import CachedLlm, load_gold, sample_answerable  # noqa: E402
from eval.results import load_manifest  # noqa: E402


class CountingLlm:
    """A cache-only Llm that counts calls and cache misses per item."""

    name = "cache-replay"

    def __init__(self, inner: CachedLlm) -> None:
        self.inner = inner
        self.calls = 0
        self.misses = 0
        self.outputs: list[str] = []

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        try:
            value = await self.inner.generate(system, prompt, context=context)
        except RuntimeError:
            self.misses += 1
            value = "cache miss"
        self.outputs.append(value)
        return value


async def replay(
    gold_path: Path,
    chunks_path: Path,
    index_dir: Path,
    cache_dir: Path,
    sample: int,
    top_k: int,
) -> int:
    reranker = (
        None
        if settings.rerank_provider == "none"
        else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        chunks_path,
        index_dir,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
    )
    retry_budget = int(load_manifest()["generation"]["retry_budget"])
    cached = CachedLlm(
        None, DEFAULT_MODEL, cache_dir, variant="temperature=0.0"
    )
    gold = load_gold(gold_path)

    answerable = sample_answerable(gold, sample)
    retried = 0
    misses = 0
    for item in answerable:
        llm = CountingLlm(cached)
        await ask(
            item.question,
            retriever=setup.retriever,
            llm=llm,
            top_k=top_k,
            max_retries=retry_budget,
        )
        misses += llm.misses
        if llm.calls > 1:
            retried += 1
            print(f"  retried {item.id}: {llm.calls} drafts")
    print(
        f"answered sample: {len(answerable)} items, {retried} retried, "
        f"{misses} cache misses"
    )

    unanswerable_retried = 0
    reasons: dict[str, int] = {}
    for item in gold:
        if item.answerable:
            continue
        llm = CountingLlm(cached)
        result = await ask(
            item.question,
            retriever=setup.retriever,
            llm=llm,
            top_k=top_k,
            max_retries=retry_budget,
        )
        misses += llm.misses
        if result.abstain_reason == "refused":
            first = llm.outputs[0] if llm.outputs else ""
            reason = (
                "refused_exact"
                if first.strip().startswith(ABSTAIN_MESSAGE)
                else "refused_paraphrase"
            )
        else:
            reason = result.abstain_reason or "answered"
        reasons[reason] = reasons.get(reason, 0) + 1
        if llm.calls > 1:
            unanswerable_retried += 1
            print(f"  unanswerable retried {item.id}")
    print(
        f"unanswerable: {unanswerable_retried} retried, {misses} total cache misses"
    )
    for reason, count in sorted(reasons.items()):
        print(f"  {reason}: {count}")
    if misses:
        print("replay is not comparable: rerun scripts/run_eval.py first")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay verification retries")
    parser.add_argument(
        "--gold", type=Path, default=REPO / "eval" / "gold" / "questions.jsonl"
    )
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--index", type=Path, default=REPO / "data" / "index" / "chroma"
    )
    parser.add_argument("--cache", type=Path, default=REPO / "eval" / ".cache")
    parser.add_argument("--sample", type=int, default=15)
    parser.add_argument("--k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args()
    return asyncio.run(
        replay(
            args.gold,
            args.chunks,
            args.index,
            args.cache,
            args.sample,
            args.k,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
