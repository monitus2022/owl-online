"""Shared node helpers: evidence formatting and token streaming."""

from collections.abc import Callable
from typing import Any

from app.pipeline.generate import render_evidence, retrieval_floor, sanitize_evidence
from app.pipeline.retrieve.strategy import classify_retrieval_strategy
from app.providers.contracts import Llm, Retriever
from app.providers.errors import ProviderError
from app.schemas import Chunk
from app.trace import current_tracer, prompt_fingerprint

Emit = Callable[[dict[str, Any]], None]


def evidence_prompt(task: str, chunks: list[Chunk], extra: str = "") -> str:
    tail = f"\n\n{extra}" if extra else ""
    return f"Excerpts:\n\n{render_evidence(chunks)}\n\nTask: {task}{tail}\n\nAnswer:"


async def retrieve_evidence(
    question: str,
    retriever: Retriever,
    top_k: int,
    min_score: float | None = None,
    strategy_question: str | None = None,
) -> list[Chunk]:
    tracer = current_tracer()
    decision = classify_retrieval_strategy(strategy_question or question)
    if tracer is not None:
        tracer.emit(
            "retrieval_strategy",
            strategy=decision.name,
            reason=decision.reason,
            cues=list(decision.cues),
        )
    span = tracer.start("retrieve") if tracer else None
    chunks = await retriever.retrieve(question, top_k)
    if tracer is not None and span is not None:
        tracer.finish(
            span,
            hits=len(chunks),
            chunk_ids=[chunk.id for chunk in chunks],
            top_score=round(chunks[0].score, 4) if chunks else None,
        )
    if not chunks or chunks[0].score < retrieval_floor(retriever, min_score):
        return []
    kept: list[Chunk] = []
    for chunk in chunks:
        cleaned, removed = sanitize_evidence(chunk.text)
        if cleaned.strip():
            kept.append(chunk.model_copy(update={"text": cleaned}) if removed else chunk)
    return kept


async def stream_text(llm: Llm, system: str, prompt: str, emit: Emit) -> str:
    tracer = current_tracer()
    span = tracer.start("generate") if tracer else None
    pieces: list[str] = []
    async for token in llm.stream(system, prompt):
        pieces.append(token)
        emit({"type": "token", "text": token})
    if tracer is not None and span is not None:
        tracer.finish(
            span,
            attempt=1,
            model=getattr(llm, "name", "?"),
            **prompt_fingerprint(system, prompt),
        )
    return "".join(pieces)


async def stream_with_fallback(
    llm: Llm,
    fallback: Llm | None,
    system: str,
    prompt: str,
    emit: Emit,
    *,
    intent: str,
) -> tuple[str, str, int]:
    """Stream from the routed model, returning text, the model used and attempts."""
    tracer = current_tracer()
    if tracer is not None and fallback is not None:
        tracer.emit(
            "route",
            intent=intent,
            model=getattr(llm, "name", "?"),
            fallback=True,
        )
    try:
        text = await stream_text(llm, system, prompt, emit)
        return text, getattr(llm, "name", "?"), 1
    except ProviderError:
        if fallback is None:
            raise
        if tracer is not None:
            tracer.emit(
                "fallback", intent=intent, model=getattr(fallback, "name", "?")
            )
        # Tokens from the failed model are already on the client. Clear the draft
        # before the fallback stream, exactly as a verification retry does.
        emit({"type": "reset", "reason": "fallback"})
        text = await stream_text(fallback, system, prompt, emit)
        return text, getattr(fallback, "name", "?"), 2
