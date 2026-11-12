"""Answer node: the existing grounded ask() path, with token streaming."""

from collections.abc import Mapping
from dataclasses import replace

from langgraph.config import get_stream_writer

from app.agent.persona import Persona, active_persona
from app.agent.state import AgentState
from app.knowledge import LoreStore
from app.pipeline.generate import DEFAULT_MAX_RETRIES, ask
from app.providers.contracts import Llm, Retriever


async def answer_node(
    state: AgentState,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int,
    min_score: float | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    multi_book: bool = False,
    persona: Persona | None = None,
    personas: Mapping[str, Persona] | None = None,
    default_subject: str | None = None,
    lore: LoreStore | None = None,
    lore_subject: str = "dada",
) -> dict[str, object]:
    writer = get_stream_writer()

    def emit(token: str) -> None:
        writer({"type": "token", "text": token})

    def reset() -> None:
        writer({"type": "reset", "reason": "retry"})

    subject = state.get("subject") or default_subject or lore_subject
    cards = personas
    if cards is None and persona is not None:
        cards = {default_subject or subject: persona}
    active = active_persona(
        subject,
        enabled=state.get("persona_enabled", True),
        personas=cards,
        default_subject=subject,
    )
    question = state.get("standalone_question") or state["question"]
    result = await ask(
        question,
        retriever=retriever,
        llm=llm,
        top_k=state.get("top_k", top_k),
        min_score=min_score,
        on_token=emit,
        on_reset=reset,
        max_retries=max_retries,
        multi_book=multi_book,
        persona_suffix=(
            active.answer_suffix() if active is not None else None
        ),
        lore=lore,
        subject=subject,
        prompt_question=state["question"],
        conversation_context=state.get("conversation_context"),
    )
    if result.abstained and active is not None:
        # Keep the abstention contract; only the user-facing line changes.
        result = replace(result, answer=active.abstain_response())
    return {
        "chunks": result.chunks,
        "answer": result.answer,
        "citations": result.citations,
        "lore_citations": result.lore_citations,
        "typed_citations": result.typed_citations,
        "lore_chars": result.lore_chars,
        "abstained": result.abstained,
        "attempts": result.attempts,
        "model_calls": result.model_calls,
        "abstain_reason": result.abstain_reason,
        "retry_reason": result.retry_reason,
    }
