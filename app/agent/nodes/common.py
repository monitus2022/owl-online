"""Shared node helpers: evidence formatting and token streaming."""

from collections.abc import Callable
from typing import Any

from app.pipeline.generate import render_evidence, retrieval_floor
from app.providers.contracts import Llm, Retriever
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
) -> list[Chunk]:
    tracer = current_tracer()
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
    return chunks


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
