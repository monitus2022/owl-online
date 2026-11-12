"""Run the lesson and multi-turn RAG fixtures against the current stack.

The runner is deliberately separate from the corpus eval: it measures lesson
selection, scope, citation and multi-turn routing, not factual F1 on the book
gold set. Faithfulness is the one judged lesson metric.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from pathlib import Path

from langgraph.graph.state import CompiledStateGraph

from app.agent import build_graph
from app.agent.memory import memory_saver
from app.agent.persona import PERSONAS
from app.api.runtime import Runtime, build_runtime
from app.config import Settings
from app.knowledge.packs import PackStore
from app.pipeline.generate import render_evidence
from app.pipeline.generate.lesson import ask_lesson, cited_book_ids, render_materials
from app.pipeline.index.builder import load_chunks
from app.providers.contracts import Llm
from app.providers.factory import make_llm
from app.schemas import Chunk
from eval.harness import FAITHFUL_SYSTEM, JUDGE_MODEL, CachedLlm, parse_faithful
from eval.persona.checks import check_citations, check_source_hashes
from eval.rag.fixtures import Conversation, LessonItem, load_conversations, load_lesson_items
from eval.rag.metrics import (
    LessonResult,
    RagReport,
    TurnResult,
    summarize_lesson,
    summarize_multiturn,
)
from eval.results import load_manifest, timestamp_run_id

EVAL_TEMPERATURE = 0.0


@dataclass(frozen=True)
class RagStack:
    """The wired pieces the runner needs; built once per run."""

    settings: Settings
    runtime: Runtime
    generator: CachedLlm
    generator_inner: Llm
    judge: CachedLlm
    judge_inner: Llm
    agent: CompiledStateGraph
    chunks_by_id: dict[str, Chunk]

    async def aclose(self) -> None:
        await self.runtime.aclose()
        for client in (self.generator_inner, self.judge_inner):
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()


async def build_stack(settings: Settings, cache_dir: Path) -> RagStack:
    """Build the runtime, the cached generator, the judge and the memory graph."""
    runtime = await build_runtime(settings)
    if runtime.lesson is None or runtime.pack_store is None:
        raise RuntimeError(
            "lesson mode is unavailable; publish the subject packs and enable OWL_LESSON_MODE"
        )
    generator_inner = make_llm(settings.provider, temperature=EVAL_TEMPERATURE)
    generator = CachedLlm(
        generator_inner,
        generator_inner.name,
        cache_dir,
        variant=f"rag-eval-temperature={EVAL_TEMPERATURE:g}",
    )
    judge_inner = make_llm("openrouter", model=JUDGE_MODEL, temperature=EVAL_TEMPERATURE)
    judge = CachedLlm(
        judge_inner,
        JUDGE_MODEL,
        cache_dir,
        variant=f"rag-judge-temperature={EVAL_TEMPERATURE:g}",
    )
    agent = build_graph(
        runtime.retriever,
        generator,
        max_retries=settings.retry_budget,
        multi_book=settings.multi_book,
        personas=PERSONAS if settings.persona else None,
        default_subject=settings.persona_subject,
        lore=runtime.lore,
        lesson=runtime.lesson,
        lesson_top_k=settings.lesson_top_k,
        lesson_min_score=settings.lesson_min_score,
        lesson_fallback=settings.lesson_fallback,
        checkpointer=memory_saver(),
        memory_window=settings.memory_window,
        memory_token_budget=settings.memory_token_budget,
    )
    chunks = load_chunks(settings.chunks_path)
    return RagStack(
        settings=settings,
        runtime=runtime,
        generator=generator,
        generator_inner=generator_inner,
        judge=judge,
        judge_inner=judge_inner,
        agent=agent,
        chunks_by_id={chunk.id: chunk for chunk in chunks},
    )


def _fixture_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _sample_lesson(results: list[LessonResult], sample: int) -> list[LessonResult]:
    """Round-robin across lesson slices, so multi-concept is not crowded out."""
    answered = [result for result in results if not result.abstained]
    if sample <= 0 or sample >= len(answered):
        return answered
    buckets: dict[str, list[LessonResult]] = {}
    for result in answered:
        buckets.setdefault(result.item.slice_name, []).append(result)
    picked: list[LessonResult] = []
    while len(picked) < sample:
        progressed = False
        for bucket in buckets.values():
            if bucket and len(picked) < sample:
                picked.append(bucket.pop(0))
                progressed = True
        if not progressed:
            break
    return picked


async def run_lesson(
    items: list[LessonItem],
    stack: RagStack,
    *,
    sample: int,
) -> list[LessonResult]:
    """Answer every lesson item, check citations, then judge a balanced sample."""
    pack_store: PackStore = stack.runtime.pack_store
    results: list[LessonResult] = []
    for item in items:
        pack = pack_store.get(item.subject)
        if pack is None:
            results.append(
                LessonResult(
                    item=item,
                    selected_material_ids=(),
                    material_citations=(),
                    citations=(),
                    book_citations=(),
                    scope=None,
                    abstained=True,
                    answer="",
                    citation_ok=False,
                    source_hash_ok=False,
                    error=f"no published pack for {item.subject}",
                )
            )
            continue
        persona = PERSONAS.get(item.subject) if stack.settings.persona else None
        try:
            result = await ask_lesson(
                item.question,
                selector=stack.runtime.lesson,
                subject=item.subject,
                llm=stack.generator,
                retriever=stack.runtime.retriever,
                fallback=stack.settings.lesson_fallback,
                top_k=stack.settings.lesson_top_k,
                min_score=stack.settings.lesson_min_score,
                max_retries=stack.settings.retry_budget,
                persona=persona,
            )
            citation_ok, _ = check_citations(
                result.answer,
                pack=pack,
                corpus_chunk_ids=set(stack.chunks_by_id),
                required=item.citation,
                abstained=result.abstained,
            )
            source_ok, _ = check_source_hashes(
                result.answer,
                pack=pack,
                chunks_by_id=stack.chunks_by_id,
            )
            book_citations = tuple(cited_book_ids(result.answer, list(result.chunks)))
            results.append(
                LessonResult(
                    item=item,
                    selected_material_ids=tuple(result.selected_material_ids),
                    material_citations=tuple(result.material_citations),
                    citations=tuple(result.citations),
                    book_citations=book_citations,
                    scope=result.scope,
                    abstained=result.abstained,
                    answer=result.answer,
                    citation_ok=citation_ok,
                    source_hash_ok=source_ok,
                    chunks=tuple(result.chunks),
                )
            )
        except Exception as error:  # noqa: BLE001 - eval records the failure
            results.append(
                LessonResult(
                    item=item,
                    selected_material_ids=(),
                    material_citations=(),
                    citations=(),
                    book_citations=(),
                    scope=None,
                    abstained=True,
                    answer="",
                    citation_ok=False,
                    source_hash_ok=False,
                    error=f"{type(error).__name__}: {error}",
                )
            )

    for result in _sample_lesson(results, sample):
        pack = pack_store.get(result.item.subject)
        if pack is None:
            continue
        materials = [
            material
            for material_id in result.selected_material_ids
            if (material := pack.find_material(material_id)) is not None
        ]
        if not materials:
            materials = [
                material
                for material_id in result.material_citations
                if (material := pack.find_material(material_id)) is not None
            ]
        if not materials and not result.chunks:
            continue
        parts: list[str] = []
        if materials:
            parts.append(f"Lesson notes:\n{render_materials(materials)}")
        if result.chunks:
            parts.append(f"Excerpts:\n{render_evidence(result.chunks)}")
        prompt = (
            "\n\n".join(parts)
            + f"\n\nQuestion: {result.item.question}\n\n"
            + f"Answer: {result.answer}"
        )
        reply = parse_faithful(await stack.judge.generate(FAITHFUL_SYSTEM, prompt))
        if reply is not None:
            results[results.index(result)] = dataclasses.replace(result, faithful=reply)
    return results


def _referral(state: dict[str, object]) -> tuple[str | None, str | None]:
    value = state.get("referral")
    if not isinstance(value, dict):
        return None, None
    subject = value.get("subject")
    concept = value.get("concept_title") or value.get("concept_id")
    return (
        subject if isinstance(subject, str) else None,
        concept if isinstance(concept, str) else None,
    )


async def run_multiturn(
    conversations: list[Conversation],
    stack: RagStack,
) -> list[TurnResult]:
    """Run each conversation on its own thread and check every turn."""
    results: list[TurnResult] = []
    for conversation in conversations:
        thread_id = f"rag-eval-{conversation.conversation_id}"
        for turn_index, turn in enumerate(conversation.turns, 1):
            initial = {
                "question": turn.question,
                "requested_mode": turn.mode,
                "subject": conversation.subject,
                "persona_enabled": stack.settings.persona,
                "top_k": 5,
            }
            try:
                state = await stack.agent.ainvoke(
                    initial,
                    config={"configurable": {"thread_id": thread_id}},
                )
                standalone = str(state.get("standalone_question") or turn.question)
                mode = str(state.get("routed_mode") or state.get("mode") or "?")
                referral_subject, referral_concept = _referral(state)
                results.append(
                    TurnResult(
                        conversation=conversation,
                        turn=turn,
                        turn_index=turn_index,
                        actual_standalone=standalone,
                        actual_mode=mode,
                        actual_material_ids=tuple(state.get("material_citations", []) or []),
                        actual_abstained=bool(state.get("abstained", False)),
                        actual_referral_subject=referral_subject,
                        actual_referral_concept=referral_concept,
                        answer=str(state.get("answer", "")),
                    )
                )
            except Exception as error:  # noqa: BLE001 - eval records the failure
                results.append(
                    TurnResult(
                        conversation=conversation,
                        turn=turn,
                        turn_index=turn_index,
                        actual_standalone="",
                        actual_mode="error",
                        actual_material_ids=(),
                        actual_abstained=True,
                        actual_referral_subject=None,
                        actual_referral_concept=None,
                        answer="",
                        error=f"{type(error).__name__}: {error}",
                    )
                )
    return results


async def run_rag_eval(
    *,
    settings: Settings,
    lesson_path: Path,
    multiturn_path: Path,
    cache_dir: Path,
    sample: int = 30,
) -> RagReport:
    """Run both fixtures and return one report."""
    items = load_lesson_items(lesson_path)
    conversations = load_conversations(multiturn_path)
    stack = await build_stack(settings, cache_dir)
    try:
        lesson_results = await run_lesson(items, stack, sample=sample)
        multiturn_results = await run_multiturn(conversations, stack)
    finally:
        await stack.aclose()
    manifest = load_manifest()
    embedder_key = "cloud" if settings.embedder_provider == "bedrock" else "local"
    retrieval = manifest["retrieval"]
    settings_payload = {
        "provider": settings.provider,
        "generator": stack.generator.name,
        "generator_temperature": EVAL_TEMPERATURE,
        "judge": JUDGE_MODEL,
        "judge_temperature": EVAL_TEMPERATURE,
        "embedder_provider": settings.embedder_provider,
        "embedder_model": manifest["embedder"][embedder_key]["model"],
        "reranker_provider": settings.rerank_provider,
        "reranker_model": settings.rerank_model,
        "rerank_pool": settings.rerank_pool,
        "rerank_min_score": settings.rerank_min_score,
        "top_k": retrieval["top_k"],
        "rrf_k": retrieval["rrf_k"],
        "candidates": retrieval["candidates"],
        "subquery_quota": settings.subquery_quota,
        "retry_budget": settings.retry_budget,
        "multi_book": settings.multi_book,
        "lesson_top_k": settings.lesson_top_k,
        "lesson_min_score": settings.lesson_min_score,
        "lesson_fallback": settings.lesson_fallback,
        "memory_window": settings.memory_window,
        "memory_token_budget": settings.memory_token_budget,
    }
    return RagReport(
        run_id=timestamp_run_id(),
        config="rag-eval",
        generator=stack.generator.name,
        judge=JUDGE_MODEL,
        lesson_sample=sample,
        lesson_fixture_sha=_fixture_sha(lesson_path),
        multiturn_fixture_sha=_fixture_sha(multiturn_path),
        settings=settings_payload,
        lesson=summarize_lesson(lesson_results),
        multiturn=summarize_multiturn(multiturn_results),
    )


__all__ = [
    "RagStack",
    "build_stack",
    "run_lesson",
    "run_multiturn",
    "run_rag_eval",
]
