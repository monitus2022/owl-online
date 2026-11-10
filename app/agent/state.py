"""LangGraph agent state: one request in, one grounded result out."""

from typing import Literal, TypedDict

from app.schemas import Chunk

Mode = Literal["answer", "practice", "feedback", "meta", "personal", "lesson"]
RequestedMode = Literal["auto", "answer", "practice", "feedback", "lesson"]


class AgentState(TypedDict, total=False):
    question: str
    requested_mode: RequestedMode
    subject: str
    persona_enabled: bool
    student_answer: str | None
    top_k: int
    mode: Mode
    meta_topic: str | None
    chunks: list[Chunk]
    answer: str
    citations: list[str]
    lore_citations: list[str]
    material_citations: list[str]
    scope: str | None
    abstained: bool
    needs_input: bool
    attempts: int
    model_calls: int
    abstain_reason: str | None
    retry_reason: str | None
    llm_model: str
    prompt_chars: int
