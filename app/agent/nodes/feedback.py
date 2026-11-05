"""Feedback node: formative feedback on a chat answer.

This is not an official exam score. Formal attempts are graded deterministically
against stored mark schemes in the exam bank.
"""

from langgraph.config import get_stream_writer

from app.agent.nodes.common import evidence_prompt, retrieve_evidence, stream_text
from app.agent.state import AgentState
from app.pipeline.generate import ABSTAIN_MESSAGE, ground_answer
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
) -> dict[str, object]:
    student = (state.get("student_answer") or "").strip()
    if not student:
        return {
            "chunks": [],
            "answer": MISSING_ANSWER,
            "citations": [],
            "abstained": True,
        }
    chunks = await retrieve_evidence(
        f"{state['question']}\n\n{student}",
        retriever,
        state.get("top_k", top_k),
        min_score,
    )
    if not chunks:
        return {
            "chunks": [],
            "answer": ABSTAIN_MESSAGE,
            "citations": [],
            "abstained": True,
        }
    prompt = evidence_prompt(
        state["question"],
        chunks,
        extra=f"Student answer:\n{student}",
    )
    text = await stream_text(llm, SYSTEM, prompt, get_stream_writer())
    result = ground_answer(text, chunks)
    return {
        "chunks": chunks,
        "answer": result.answer,
        "citations": result.citations,
        "abstained": result.abstained,
    }
