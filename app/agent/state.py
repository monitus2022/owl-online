"""LangGraph agent state: one request in, one grounded result out."""

from typing import Literal, TypedDict

from app.schemas import Chunk

Mode = Literal[
    "answer",
    "practice",
    "feedback",
    "meta",
    "personal",
    "lesson",
    "fact",
    "clarify",
    "policy",
    "abstain",
]
RequestedMode = Literal["auto", "answer", "practice", "feedback", "lesson"]


class AgentState(TypedDict, total=False):
    question: str
    standalone_question: str
    messages: list[dict[str, str]]
    summary: str
    conversation_context: str
    last_entity: str
    last_person: str
    last_place: str
    last_mode: str
    pending_clarify: bool
    forced_mode: str | None
    preferred_mode: str | None
    routed_mode: str
    requested_mode: RequestedMode
    subject: str
    persona_enabled: bool
    student_answer: str | None
    top_k: int
    mode: Mode
    meta_topic: str | None
    fact_ids: list[str]
    chunks: list[Chunk]
    answer: str
    citations: list[str]
    lore_citations: list[str]
    material_citations: list[str]
    typed_citations: list[str]
    scope: str | None
    abstained: bool
    needs_input: bool
    attempts: int
    model_calls: int
    abstain_reason: str | None
    retry_reason: str | None
    llm_model: str
    prompt_chars: int
