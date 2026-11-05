"""Answer node: the existing grounded ask() path, with token streaming."""

from langgraph.config import get_stream_writer

from app.agent.state import AgentState
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
    )
    return {
        "chunks": result.chunks,
        "answer": result.answer,
        "citations": result.citations,
        "abstained": result.abstained,
        "attempts": result.attempts,
        "retry_reason": result.retry_reason,
    }
