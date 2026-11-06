"""Ablate per-book k and extraction selection for the multi-book spike (#105).

Develop fixture only. For each configuration this runs the multi-book answer
path, judges the answer body for faithfulness, and reports coverage,
completeness, citation validity, faithfulness, latency and spend.

Run:
  uv run python scripts/measure_multibook_ablation.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import measure_multibook_generation as mbgen  # noqa: E402

from app.config import settings  # noqa: E402
from app.pipeline.generate.multibook import (  # noqa: E402
    DEFAULT_FINAL_TOP_K,
    DEFAULT_SELECTION_FLOOR,
    ask_multi_book,
)
from app.pipeline.index.builder import load_chunks  # noqa: E402
from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder, make_llm, make_reranker  # noqa: E402
from eval.harness import CachedLlm, load_aggregation, missing_entities  # noqa: E402
from eval.harness.judging import JUDGE_MODEL  # noqa: E402
from eval.results import load_manifest  # noqa: E402

# The workplan grid, plus the shipped k=15 per-book control.
K_VALUES = (1, 3, 5)
SELECTIONS = ("top1_floor", "batched_top3", "per_book")
CONTROL = (15, "per_book")


@dataclass(frozen=True)
class ConfigScore:
    """One configuration's aggregate result."""

    label: str
    per_book_k: int
    selection: str
    coverage: float
    completeness: float
    text_coverage: float
    text_completeness: float
    citation_validity: float
    faithfulness: float
    faithfulness_n: int
    abstention: float
    mean_calls: float
    p50_ms: float
    p95_ms: float
    spend_usd: float


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _label(per_book_k: int, selection: str) -> str:
    short = {
        "top1_floor": "top1",
        "batched_top3": "batch",
        "per_book": "book",
    }[selection]
    return f"k{per_book_k}-{short}"


async def _score_config(
    *,
    items,
    retriever,
    by_id,
    llm,
    judge,
    per_book_k: int,
    selection: str,
) -> ConfigScore:
    scores: list[mbgen.ItemScore] = []
    for item in items:
        llm.reset()
        start = time.perf_counter()
        result = await ask_multi_book(
            item.question,
            retriever=retriever,
            llm=llm,
            top_k=DEFAULT_FINAL_TOP_K,
            per_book_k=per_book_k,
            selection=selection,
            selection_floor=DEFAULT_SELECTION_FLOOR,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        cited_chunks = [by_id[cid] for cid in result.citations if cid in by_id]
        books_expected, books_covered, entities_expected, entities_found = (
            mbgen._cited_coverage(item, cited_chunks)
        )
        (
            _,
            answer_books_covered,
            _,
            answer_entities_found,
        ) = mbgen._answer_coverage(item, result.answer)
        valid = sum(mbgen._is_relevant(item, chunk) for chunk in cited_chunks)
        body = result.answer.split("\n\nCoverage:")[0]
        faithful = (
            None
            if result.abstained
            else await mbgen._faithful(judge, item, body, result.chunks)
        )
        scores.append(
            mbgen.ItemScore(
                item_id=item.id,
                kind=item.kind,
                routed="multi_book",
                abstained=result.abstained,
                books_expected=books_expected,
                books_covered=books_covered,
                entities_expected=entities_expected,
                entities_found=entities_found,
                answer_books_covered=answer_books_covered,
                answer_entities_found=answer_entities_found,
                citations=len(result.citations),
                valid_citations=valid,
                faithful=faithful,
                latency_ms=latency_ms,
                model_calls=result.model_calls,
                input_chars=llm.input_chars,
                output_chars=llm.output_chars,
            )
        )

    coverage = _mean([s.books_covered / s.books_expected for s in scores])
    completeness = _mean([s.entities_found / s.entities_expected for s in scores])
    text_coverage = _mean([s.answer_books_covered / s.books_expected for s in scores])
    text_completeness = _mean(
        [s.answer_entities_found / s.entities_expected for s in scores]
    )
    citations = sum(s.citations for s in scores)
    valid = sum(s.valid_citations for s in scores)
    judged = [s for s in scores if not s.abstained]
    faithful = _mean([1.0 if s.faithful else 0.0 for s in judged])
    latencies = [s.latency_ms for s in scores]
    calls = _mean([float(s.model_calls) for s in scores])
    input_tokens = sum(s.input_chars for s in scores) // 4
    output_tokens = sum(s.output_chars for s in scores) // 4
    spend = (
        input_tokens * settings.chat_input_price_per_mtok
        + output_tokens * settings.chat_output_price_per_mtok
    ) / 1_000_000
    return ConfigScore(
        label=_label(per_book_k, selection),
        per_book_k=per_book_k,
        selection=selection,
        coverage=coverage,
        completeness=completeness,
        text_coverage=text_coverage,
        text_completeness=text_completeness,
        citation_validity=valid / citations if citations else 0.0,
        faithfulness=faithful,
        faithfulness_n=len(judged),
        abstention=_mean([1.0 if s.abstained else 0.0 for s in scores]),
        mean_calls=calls,
        p50_ms=median(latencies) if latencies else 0.0,
        p95_ms=_p95(latencies),
        spend_usd=spend,
    )


async def run(args) -> int:
    items = load_aggregation(args.fixture)
    multi = [item for item in items if item.kind == "multi_book"]
    corpus = load_chunks(args.chunks)
    missing = missing_entities(items, corpus)
    if missing:
        print("fixture entities missing from the corpus:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    by_id = mbgen._chunk_index(corpus)

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
    llm = mbgen._CountingLlm(make_llm("openrouter", temperature=0.0))
    judge = CachedLlm(
        make_llm("openrouter", model=JUDGE_MODEL, temperature=0.0),
        JUDGE_MODEL,
        args.cache,
        variant="temperature=0.0",
    )
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    configs = [(k, selection) for k in K_VALUES for selection in SELECTIONS]
    configs.append(CONTROL)
    results: list[ConfigScore] = []
    try:
        for per_book_k, selection in configs:
            print(
                f"running {_label(per_book_k, selection)} "
                f"(k={per_book_k}, selection={selection})...",
                flush=True,
            )
            results.append(
                await _score_config(
                    items=multi,
                    retriever=setup.retriever,
                    by_id=by_id,
                    llm=llm,
                    judge=judge,
                    per_book_k=per_book_k,
                    selection=selection,
                )
            )
    finally:
        await setup.retriever.aclose()

    manifest = load_manifest()
    embedder_key = "cloud" if settings.embedder_provider == "bedrock" else "local"
    print()
    print(f"run: {run_id}")
    print(f"fixture: {args.fixture}")
    print(f"items: {len(multi)} multi_book")
    print(
        f"manifest: generator={manifest['generator']['model']} "
        f"judge={JUDGE_MODEL} reranker={manifest['reranker']['model']} "
        f"pool={settings.rerank_pool} "
        f"embedder={manifest['embedder'][embedder_key]['model']} "
        f"final_top_k={DEFAULT_FINAL_TOP_K} "
        f"selection_floor={DEFAULT_SELECTION_FLOOR}"
    )
    print()
    header = (
        "config          cov  comp  text  cite  faith  n  abst  calls  "
        "p50ms  p95ms  spend"
    )
    print(header)
    for score in results:
        print(
            f"{score.label:14} "
            f"{score.coverage:4.2f} {score.completeness:5.2f} "
            f"{score.text_coverage:5.2f} {score.citation_validity:5.2f} "
            f"{score.faithfulness:5.2f} {score.faithfulness_n:2} "
            f"{score.abstention:5.2f} {score.mean_calls:5.1f} "
            f"{score.p50_ms:6.0f} {score.p95_ms:6.0f} "
            f"${score.spend_usd:.4f}"
        )

    args.cache.mkdir(parents=True, exist_ok=True)
    out = args.cache / f"{run_id}-multibook-ablation.json"
    out.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "fixture": str(args.fixture),
                "items": len(multi),
                "generator": manifest["generator"]["model"],
                "judge": JUDGE_MODEL,
                "configs": [score.__dict__ for score in results],
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
        description="Ablate multi-book k and selection on the develop fixture"
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
    parser.add_argument(
        "--cache", type=Path, default=REPO / "eval" / ".cache"
    )
    parser.add_argument("--run-id", default=None)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
