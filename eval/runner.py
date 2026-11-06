"""Run the eval end to end: compose the stack, score it, write the CSV."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings
from app.pipeline.index.builder import load_chunks
from app.pipeline.retrieve import compose_retriever
from app.providers.factory import make_embedder, make_llm, make_reranker
from app.providers.openrouter import DEFAULT_MODEL
from eval.harness import (
    JUDGE_MODEL,
    CachedLlm,
    abstention_metrics_all,
    corpus_vocabulary,
    generation_metrics_by_slice,
    judge_sample,
    load_gold,
    retrieval_diagnostics_all,
    retrieval_metrics_all,
    summarize_generation,
    summarize_novelty,
)
from eval.report import (
    RunReport,
    abstention_rows,
    generation_rows,
    novelty_rows,
    retrieval_diagnostic_rows,
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
    embedder_model: str | None = None,
) -> RunReport:
    """Score the pinned stack, write one result CSV, and optionally pin it."""
    reranker = (
        None if settings.rerank_provider == "none" else make_reranker(settings.rerank_provider)
    )
    setup = await compose_retriever(
        chunks_path,
        index_dir,
        make_embedder(settings.embedder_provider, model=embedder_model),
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
        subquery_quota=settings.subquery_quota,
    )
    # The eval needs real hosted models; the judge is pinned to OpenRouter.
    temperature = 0.0
    generator = CachedLlm(
        make_llm("openrouter", temperature=temperature),
        DEFAULT_MODEL,
        cache_dir,
        variant=f"temperature={temperature}",
    )
    judge = CachedLlm(
        make_llm("openrouter", model=JUDGE_MODEL, temperature=temperature),
        JUDGE_MODEL,
        cache_dir,
        variant=f"temperature={temperature}",
    )
    gold = load_gold(gold_path)
    gold_hash = hashlib.sha256(gold_path.read_bytes()).hexdigest()[:12]
    manifest = load_manifest()
    # Pinned in config/manifest.toml and asserted by eval/test_manifest.py.
    retry_budget = int(manifest["generation"]["retry_budget"])

    retrieval, retrieval_by_slice = await retrieval_metrics_all(setup.retriever, gold, k)
    diagnostics, diagnostics_by_slice = await retrieval_diagnostics_all(
        setup.retriever, gold, k
    )
    abstention, abstention_by_slice = await abstention_metrics_all(
        setup.retriever, generator, gold, k, retry_budget
    )
    verdicts = await judge_sample(
        setup.retriever, generator, judge, gold, sample, k, retry_budget
    )
    generation = summarize_generation(verdicts)
    generation_by_slice = generation_metrics_by_slice(verdicts, gold)
    vocabulary = corpus_vocabulary(load_chunks(chunks_path))
    novelty = summarize_novelty(
        [verdict.answer for verdict in verdicts if not verdict.abstained], vocabulary
    )

    run_id = timestamp_run_id()
    if reranker is None:
        config = "no-rerank"
    elif embedder_model is not None:
        config = "custom-embedder"
    elif chunks_path.name != "chunks.jsonl" or index_dir.name != "chroma":
        config = "context"
    else:
        config = "pinned"
    values = manifest_row(
        manifest,
        embedder_provider=settings.embedder_provider,
        rerank_enabled=reranker is not None,
        top_k=k,
        reranker_pool=settings.rerank_pool if reranker is not None else None,
        candidates=settings.rerank_pool if reranker is not None else None,
        judged_sample=sample,
        reranker_model=settings.rerank_model if reranker is not None else None,
        embedder_model=(
            embedder_model
            or (
                settings.bedrock_embed_model
                if settings.embedder_provider == "bedrock"
                else None
            )
        ),
        embedder_dims=setup.dims,
        gold_hash=gold_hash,
        index_text_hash=setup.text_hash,
        rerank_min_score=settings.rerank_min_score,
        generator_temperature=temperature,
        judge_temperature=temperature,
    )
    rows = [
        *retrieval_rows(run_id, config, values, retrieval, retrieval_by_slice),
        *retrieval_diagnostic_rows(
            run_id, config, values, diagnostics, diagnostics_by_slice
        ),
        *abstention_rows(run_id, config, values, abstention, abstention_by_slice),
        *generation_rows(run_id, config, values, generation, generation_by_slice),
        *novelty_rows(run_id, config, values, novelty),
    ]
    run_path = results_dir / f"{run_id}.csv"
    if run_path.exists():
        raise FileExistsError(
            f"{run_path} already exists; wait for the next second and rerun"
        )
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
        novelty=novelty,
        diagnostics=diagnostics,
        diagnostics_by_slice=diagnostics_by_slice,
    )