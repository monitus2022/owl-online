"""Feedback node: formative feedback on a chat answer.

This is not an official exam score. Formal attempts are graded deterministically
against stored mark schemes in the exam bank.
"""

from langgraph.config import get_stream_writer

from app.agent.nodes.common import (
    evidence_prompt,
    retrieve_evidence,
    stream_with_fallback,
)
from app.agent.state import AgentState
from app.pipeline.generate import ABSTAIN_MESSAGE, CONVERSATION_NOTE, ground_answer
from app.providers.contracts import Llm, Retriever

MISSING_ANSWER = "I need the answer you want feedback on."

SYSTEM = (
    "You are O.W.L. Online, a revision coach. Give formative feedback on the "
    "student's answer using only the excerpts. Say what is right, what is "
    "missing, and give a provisional mark out of 10. This is not an official "
    "exam score. Cite the id of every excerpt you rely on in square brackets, "
    "exactly as given. If the excerpts cannot support a judgement, reply exactly: "
    f"{ABSTAIN_MESSAGE}"
)


async def feedback_node(
    state: AgentState,
    *,
    retriever: Retriever,
    llm: Llm,
    top_k: int,
    min_score: float | None = None,
    fallback_llm: Llm | None = None,
) -> dict[str, object]:
    student = (state.get("student_answer") or "").strip()
    if not student:
        return {
            "chunks": [],
            "answer": MISSING_ANSWER,
            "citations": [],
            "typed_citations": [],
            "abstained": False,
            "needs_input": True,
        }
    question = state.get("standalone_question") or state["question"]
    chunks = await retrieve_evidence(
        f"{question}\n\n{student}",
        retriever,
        state.get("top_k", top_k),
        min_score,
        strategy_question=question,
    )
    if not chunks:
        return {
            "chunks": [],
            "answer": ABSTAIN_MESSAGE,
            "citations": [],
            "typed_citations": [],
            "abstained": True,
        }
    prompt = evidence_prompt(
        state["question"],
        chunks,
        extra=f"Student answer:\n{student}",
        context=state.get("conversation_context", ""),
    )
    system = SYSTEM
    if state.get("conversation_context"):
        system = f"{SYSTEM}\n\n{CONVERSATION_NOTE}"
    text, model_used, attempts = await stream_with_fallback(
        llm,
        fallback_llm,
        system,
        prompt,
        get_stream_writer(),
        intent="feedback",
    )
    result = ground_answer(text, chunks)
    return {
        "chunks": chunks,
        "answer": result.answer,
        "citations": result.citations,
        "typed_citations": result.typed_citations,
        "abstained": result.abstained,
        "llm_model": model_used,
        "attempts": attempts,
    }
