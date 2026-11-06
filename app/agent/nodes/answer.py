"""Answer node: the existing grounded ask() path, with token streaming."""

from dataclasses import replace

from langgraph.config import get_stream_writer

from app.agent.persona import Persona
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
    lore: LoreStore | None = None,
    lore_subject: str = "dada",
) -> dict[str, object]:
    writer = get_stream_writer()

    def emit(token: str) -> None:
        writer({"type": "token", "text": token})

    def reset() -> None:
        writer({"type": "reset", "reason": "retry"})

    result = await ask(
        state["question"],
        retriever=retriever,
        llm=llm,
        top_k=state.get("top_k", top_k),
        min_score=min_score,
        on_token=emit,
        on_reset=reset,
        max_retries=max_retries,
        multi_book=multi_book,
        persona_suffix=persona.answer_suffix() if persona is not None else None,
        lore=lore,
        subject=lore_subject,
    )
    if result.abstained and persona is not None:
        # Keep the abstention contract; only the user-facing line changes.
        result = replace(result, answer=persona.abstain_response())
    return {
        "chunks": result.chunks,
        "answer": result.answer,
        "citations": result.citations,
        "lore_citations": result.lore_citations,
        "abstained": result.abstained,
        "attempts": result.attempts,
        "model_calls": result.model_calls,
        "abstain_reason": result.abstain_reason,
        "retry_reason": result.retry_reason,
    }
