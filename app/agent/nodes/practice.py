"""Practice node: write a grounded question or two for chat.

This is conversational practice, not a formal exam. It is not persisted and it
is not the static exam bank.
"""

from langgraph.config import get_stream_writer

from app.agent.nodes.common import (
    evidence_prompt,
    retrieve_evidence,
    stream_with_fallback,
)
from app.agent.state import AgentState
from app.pipeline.generate import ABSTAIN_MESSAGE, ground_answer
from app.providers.contracts import Llm, Retriever

SYSTEM = (
    "You are O.W.L. Online, a revision coach. Use only the excerpts provided. "
    "Write one or two short practice questions on the requested topic, with a "
    "brief answer or marking points. Cite the id of every excerpt you use in "
    "square brackets, exactly as given. This is conversational practice, not a "
    "formal exam. If the excerpts cannot support the request, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)


async def practice_node(
    state: AgentState,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int,
    min_score: float | None = None,
    fallback_llm: Llm | None = None,
) -> dict[str, object]:
    chunks = await retrieve_evidence(
        state["question"], retriever, state.get("top_k", top_k), min_score
    )
    if not chunks:
        return {
            "chunks": [],
            "answer": ABSTAIN_MESSAGE,
            "citations": [],
            "abstained": True,
        }
    prompt = evidence_prompt(state["question"], chunks)
    text, model_used, attempts = await stream_with_fallback(
        llm,
        fallback_llm,
        SYSTEM,
        prompt,
        get_stream_writer(),
        intent="practice",
    )
    result = ground_answer(text, chunks)
    return {
        "chunks": chunks,
        "answer": result.answer,
        "citations": result.citations,
        "abstained": result.abstained,
        "llm_model": model_used,
        "attempts": attempts,
    }
