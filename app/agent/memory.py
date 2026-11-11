"""Short-term conversation memory for the chat graph (#30).

The router stays authoritative: memory resolves a referent or consumes a
pending clarify, but it never changes the answer contract. A persona follow-up
stays persona, a teaching follow-up stays teaching. The thread state lives in
the graph checkpointer (process memory) and resets on restart.

The context is bounded twice: a recent message window and a rolling summary
under a character/token budget. The resolver is deterministic; a model rewrite
is deliberately out of scope for this slice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.knowledge.taxonomy import SUBJECT_NAMES

WINDOW_MESSAGES = 6
TOKEN_BUDGET = 1200
_CHARS_PER_TOKEN = 4

_WHO = re.compile(r"^\s*who is\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHAT = re.compile(r"^\s*what is\s+(?:a |an |the )?(.+?)[?.!]*\s*$", re.IGNORECASE)
_TELL = re.compile(r"^\s*tell me about\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHERE = re.compile(r"^\s*where is\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_GO = re.compile(r"^\s*did you go to\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHAT_ABOUT = re.compile(r"^\s*what about\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_PRONOUN = re.compile(r"\b(him|her|them|they|he|she)\b", re.IGNORECASE)
_THERE = re.compile(r"\bthere\b", re.IGNORECASE)
_EXAM = re.compile(
    r"\b(exams?|examinations?|tests?|assessments?|papers?|grading|"
    r"mark schemes?|marks?)\b",
    re.IGNORECASE,
)
_SCOPE = re.compile(
    r"\b(topics?|cover|covers|include|includes|subject|curriculum|syllabus)\b",
    re.IGNORECASE,
)


def memory_saver() -> MemorySaver:
    """The process-local checkpointer, with the state chunk type allowlisted.

    The graph stores retrieved ``Chunk`` objects in state. LangGraph's default
    serializer warns about unregistered types and will block them in a future
    release, so name the one type the state carries.
    """
    return MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=[("app.schemas", "Chunk")]))


@dataclass(frozen=True)
class Resolution:
    """The standalone query and an optional forced contract mode."""

    standalone: str
    forced_mode: str | None = None


def extract_entity(question: str) -> str | None:
    """The named entity a follow-up pronoun is likely to refer to."""
    for pattern in (_WHO, _TELL, _WHERE, _GO):
        match = pattern.match(question)
        if match:
            return match.group(1).strip()
    match = _WHAT.match(question)
    if match:
        return match.group(1).strip()
    return None


def _entity_from_messages(messages: list[dict[str, str]]) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        entity = extract_entity(message.get("content", ""))
        if entity:
            return entity
    return None


def _entity_from_summary(summary: str) -> str | None:
    for segment in reversed(summary.split("Earlier:")):
        entity = extract_entity(segment.strip())
        if entity:
            return entity
    return None


def resolve_followup(
    question: str,
    *,
    messages: list[dict[str, str]] | None = None,
    summary: str = "",
    last_entity: str | None = None,
    last_mode: str | None = None,
    pending_clarify: bool = False,
    subject: str = "dada",
) -> Resolution:
    """Resolve a follow-up against the thread state without changing authority."""
    text = question.strip()
    if pending_clarify:
        if _EXAM.search(text):
            return Resolution(text, forced_mode="policy")
        if _SCOPE.search(text):
            name = SUBJECT_NAMES.get(subject, subject)
            return Resolution(f"What does {name} cover?")
        return Resolution(text, forced_mode="clarify")

    entity = last_entity or _entity_from_messages(messages or []) or _entity_from_summary(summary)
    if entity:
        if _PRONOUN.search(text):
            return Resolution(_PRONOUN.sub(entity, text, count=1))
        if _THERE.search(text):
            return Resolution(_THERE.sub(entity, text, count=1))

    match = _WHAT_ABOUT.match(text)
    if match:
        target = match.group(1).strip()
        if last_mode in {"lesson", "answer"}:
            return Resolution(f"What is {target}?")
        return Resolution(f"Tell me about {target}.")

    return Resolution(text)


def trim_history(
    messages: list[dict[str, str]],
    summary: str,
    *,
    window: int = WINDOW_MESSAGES,
    token_budget: int = TOKEN_BUDGET,
) -> tuple[list[dict[str, str]], str]:
    """Keep the recent window and fold older user turns into a short summary."""
    if window < 1:
        window = 1
    kept = messages[-window:]
    older = messages[:-window]
    if older:
        lines = [
            message["content"].strip()
            for message in older
            if message.get("role") == "user" and message.get("content", "").strip()
        ]
        extra = " ".join(f"Earlier: {line}" for line in lines)
        summary = f"{summary} {extra}".strip() if summary else extra
    limit = max(1, token_budget) * _CHARS_PER_TOKEN
    if len(summary) > limit:
        summary = summary[-limit:]
    while kept and context_chars(kept, summary) > limit:
        dropped = kept.pop(0)
        if dropped.get("role") == "user" and dropped.get("content", "").strip():
            summary = f"{summary} Earlier: {dropped['content'].strip()}".strip()
        if len(summary) > limit:
            summary = summary[-limit:]
    return kept, summary


def context_chars(messages: list[dict[str, str]], summary: str) -> int:
    """Approximate prompt characters for the bounded memory context."""
    return len(summary) + sum(len(message.get("content", "")) for message in messages)


__all__ = [
    "Resolution",
    "TOKEN_BUDGET",
    "WINDOW_MESSAGES",
    "context_chars",
    "extract_entity",
    "memory_saver",
    "resolve_followup",
    "trim_history",
]
