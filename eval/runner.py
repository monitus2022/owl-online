"""Run the eval end to end: compose the stack, score it, write the CSV."""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.pipeline.retrieve import compose_retriever
from app.providers.factory import make_embedder, make_llm, make_reranker
from app.providers.openrouter import DEFAULT_MODEL
from eval.harness import (
    JUDGE_MODEL,
    CachedLlm,
    abstention_metrics_all,
    generation_metrics_by_slice,
    judge_sample,
    load_gold,
    retrieval_metrics_all,
    summarize_generation,
)
from eval.report import (
    RunReport,
    abstention_rows,
    generation_rows,
    retrieval_rows,
)
from eval.results import (
    copy_baseline,
    load_manifest,
    manifest_row,
    timestamp_run_id,
    write_results,
)


async def run(
    *,
    gold_path: Path,
    chunks_path: Path,
    index_dir: Path,
    cache_dir: Path,
    results_dir: Path,
    baseline: Path,
    k: int,
    sample: int,
    pin_baseline: bool,
) -> RunReport:
    """Score the pinned stack, write one result CSV, and optionally pin it."""
    reranker = (
        None if settings.rerank_provider == "none" else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        chunks_path,
        index_dir,
        make_embedder(settings.embedder_provider),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
    )
    # The eval needs real hosted models; the judge is pinned to OpenRouter.
    generator = CachedLlm(make_llm("openrouter"), DEFAULT_MODEL, cache_dir)
    judge = CachedLlm(make_llm("openrouter", model=JUDGE_MODEL), JUDGE_MODEL, cache_dir)
    gold = load_gold(gold_path)

    retrieval, retrieval_by_slice = await retrieval_metrics_all(setup.retriever, gold, k)
    abstention, abstention_by_slice = await abstention_metrics_all(
        setup.retriever, generator, gold, k
    )
    verdicts = await judge_sample(setup.retriever, generator, judge, gold, sample, k)
    generation = summarize_generation(verdicts)
    generation_by_slice = generation_metrics_by_slice(verdicts, gold)

    run_id = timestamp_run_id()
    config = "pinned" if reranker is not None else "no-rerank"
    manifest = load_manifest()
    values = manifest_row(
        manifest,
        embedder_provider=settings.embedder_provider,
        rerank_enabled=reranker is not None,
        top_k=k,
        reranker_pool=settings.rerank_pool if reranker is not None else None,
        candidates=settings.rerank_pool if reranker is not None else None,
    )
    rows = [
        *retrieval_rows(run_id, config, values, retrieval, retrieval_by_slice),
        *abstention_rows(run_id, config, values, abstention, abstention_by_slice),
        *generation_rows(run_id, config, values, generation, generation_by_slice),
    ]
    run_path = results_dir / f"{run_id}.csv"
    write_results(run_path, rows)

    pinned: Path | None = None
    if pin_baseline:
        copy_baseline(run_path, baseline)
        pinned = baseline

    return RunReport(
        run_path=run_path,
        baseline_path=pinned,
        config=config,
        generator=f"openrouter/{DEFAULT_MODEL}",
        judge=f"openrouter/{JUDGE_MODEL}",
        reranker=settings.rerank_provider if reranker is not None else "none",
        gold_total=len(gold),
        answerable=retrieval.n,
        unanswerable=abstention.n,
        k=k,
        retrieval=retrieval,
        retrieval_by_slice=retrieval_by_slice,
        abstention=abstention,
        abstention_by_slice=abstention_by_slice,
        generation=generation,
        generation_by_slice=generation_by_slice,
    )