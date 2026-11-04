"""Run the O.W.L. mini-eval and print the metrics.

Run: uv run python scripts/run_eval.py
Params and printing only; the logic lives in eval.harness. Generation and judge
outputs are cached under eval/.cache by (model, input).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_llm  # noqa: E402
from app.providers.openrouter import DEFAULT_MODEL  # noqa: E402
from eval.harness import (  # noqa: E402
    JUDGE_MODEL,
    CachedLlm,
    abstention_metrics,
    judge_sample,
    load_gold,
    retrieval_metrics,
)


async def _run(args: argparse.Namespace) -> int:
    setup = await compose_retriever(args.chunks, args.index, make_embedder("local"))
    generator = CachedLlm(make_llm("openrouter"), DEFAULT_MODEL, args.cache)
    judge = CachedLlm(make_llm("openrouter", model=JUDGE_MODEL), JUDGE_MODEL, args.cache)
    gold = load_gold(args.gold)

    retrieval = await retrieval_metrics(setup.retriever, gold, args.k)
    abstention = await abstention_metrics(setup.retriever, generator, gold)
    verdicts = await judge_sample(setup.retriever, generator, judge, gold, args.sample)

    correct = sum(v.correctness == "correct" for v in verdicts)
    partial = sum(v.correctness == "partial" for v in verdicts)
    wrong = sum(v.correctness == "wrong" for v in verdicts)
    abstained = sum(v.abstained for v in verdicts)
    grounded = sum(v.grounded for v in verdicts)

    print(f"gold: {len(gold)} items ({retrieval.n} answerable, {abstention.n} unanswerable)")
    print(f"generator: openrouter/{DEFAULT_MODEL}")
    print(f"judge: openrouter/{JUDGE_MODEL}")
    print()
    print(f"Hit@{args.k}: {retrieval.hit_at_k:.2f}")
    print(f"Recall@{args.k}: {retrieval.recall_at_k:.2f}")
    print(f"MRR: {retrieval.mrr:.2f}")
    print(f"Abstention (unanswerable): {abstention.refused}/{abstention.n} ({abstention.rate:.2f})")
    print()
    print(
        f"judged sample: {len(verdicts)} "
        f"(correct {correct}, partial {partial}, wrong {wrong}, abstained {abstained})"
    )
    print(f"grounded: {grounded}/{len(verdicts)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the O.W.L. mini-eval")
    parser.add_argument("--gold", type=Path, default=REPO / "eval" / "gold" / "questions.jsonl")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index" / "chroma")
    parser.add_argument("--cache", type=Path, default=REPO / "eval" / ".cache")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
