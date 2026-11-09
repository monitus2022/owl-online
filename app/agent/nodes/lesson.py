"""Lesson node: the pack-grounded teaching path, with token streaming."""

from dataclasses import replace

from langgraph.config import get_stream_writer

from app.agent.persona import Persona
from app.agent.state import AgentState
from app.knowledge.lesson import LessonSelector
from app.pipeline.generate.lesson import ask_lesson
from app.providers.contracts import Llm, Retriever


async def lesson_node(
    state: AgentState,
    *,
    selector: LessonSelector,
    retriever: Retriever,
    llm: Llm,
    subject: str,
    top_k: int,
    min_score: float | None = None,
    max_retries: int = 1,
    persona: Persona | None = None,
    fallback: bool = True,
) -> dict[str, object]:
    writer = get_stream_writer()

    def emit(token: str) -> None:
        writer({"type": "token", "text": token})

    def reset() -> None:
        writer({"type": "reset", "reason": "retry"})

    result = await ask_lesson(
        state["question"],
        selector=selector,
        subject=subject,
        llm=llm,
        retriever=retriever,
        fallback=fallback,
        top_k=top_k,
        min_score=min_score,
        on_token=emit,
        on_reset=reset,
        max_retries=max_retries,
        persona_suffix=persona.answer_suffix() if persona is not None else None,
    )
    if result.abstained and persona is not None:
        # Keep the abstention contract; only the user-facing line changes.
        result = replace(result, answer=persona.abstain_response())
    return {
        "chunks": result.chunks,
        "answer": result.answer,
        "citations": result.citations,
        "material_citations": result.material_citations,
        "scope": result.scope,
        "abstained": result.abstained,
        "attempts": result.attempts,
        "model_calls": result.model_calls,
        "abstain_reason": result.abstain_reason,
        "retry_reason": result.retry_reason,
        "prompt_chars": result.prompt_chars,
    }
