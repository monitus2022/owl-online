"""LangGraph agent state: one request in, one grounded result out."""

from typing import Literal, TypedDict

from app.schemas import Chunk

Mode = Literal["answer", "practice", "feedback"]
RequestedMode = Literal["auto", "answer", "practice", "feedback"]


class AgentState(TypedDict, total=False):
    question: str
    requested_mode: RequestedMode
    student_answer: str | None
    top_k: int
    mode: Mode
    chunks: list[Chunk]
    answer: str
    citations: list[str]
    abstained: bool
    needs_input: bool
