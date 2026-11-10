"""Lesson node: the pack-grounded teaching path, with token streaming."""

from collections.abc import Mapping
from dataclasses import replace

from langgraph.config import get_stream_writer

from app.agent.persona import Persona, active_persona
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
    personas: Mapping[str, Persona] | None = None,
    default_subject: str | None = None,
    fallback: bool = True,
) -> dict[str, object]:
    writer = get_stream_writer()

    def emit(token: str) -> None:
        writer({"type": "token", "text": token})

    def reset() -> None:
        writer({"type": "reset", "reason": "retry"})

    active_subject = state.get("subject") or default_subject or subject
    cards = personas
    if cards is None and persona is not None:
        cards = {active_subject: persona}
    active = active_persona(
        active_subject,
        enabled=state.get("persona_enabled", True),
        personas=cards,
        default_subject=active_subject,
    )
    result = await ask_lesson(
        state["question"],
        selector=selector,
        subject=active_subject,
        llm=llm,
        retriever=retriever,
        fallback=fallback,
        top_k=top_k,
        min_score=min_score,
        on_token=emit,
        on_reset=reset,
        max_retries=max_retries,
        persona=active,
    )
    if result.abstained and active is not None:
        # Keep the abstention contract; only the user-facing line changes.
        result = replace(result, answer=active.abstain_response())
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
