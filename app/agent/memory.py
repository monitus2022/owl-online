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
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.knowledge.taxonomy import SUBJECT_NAMES

WINDOW_MESSAGES = 6
TOKEN_BUDGET = 1200
_CHARS_PER_TOKEN = 4

EntityKind = Literal["person", "place", "thing"]

_WHO = re.compile(r"^\s*who(?:'s| is| was)\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHAT = re.compile(
    r"^\s*(?:what's|what is|what are|what do you know about)\s+"
    r"(?:a |an |the )?(.+?)[?.!]*\s*$",
    re.IGNORECASE,
)
_TELL = re.compile(r"^\s*tell me about\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHERE = re.compile(r"^\s*where is\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_GO = re.compile(r"^\s*did you go to\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_WHAT_ABOUT = re.compile(r"^\s*what about\s+(.+?)[?.!]*\s*$", re.IGNORECASE)
_PERSON_PRONOUN = re.compile(r"\b(him|her|he|she)\b", re.IGNORECASE)
_THEY = re.compile(r"\b(them|they)\b", re.IGNORECASE)
_THERE = re.compile(r"\bthere\b", re.IGNORECASE)
_THERE_QUESTION = re.compile(
    r"\b(is|are|was|were)\s+there\s+(a|an|any|some|something|anything)\b",
    re.IGNORECASE,
)
_NEW_QUESTION = re.compile(
    r"^\s*(who|what|when|where|why|how|which|whose|did|do|does|is|are|was|"
    r"were|can|could|should|would|tell me|give me|show me|explain|describe|"
    r"compare|teach me|quiz me|test me)\b",
    re.IGNORECASE,
)
_PRACTICE = re.compile(
    r"\b(test me|quiz me|give me (?:a |some )?practice|practice questions?)\b",
    re.IGNORECASE,
)
_EXAM = re.compile(
    r"\b(exams?|examinations?|tests?|assessments?|papers?|grading|"
    r"mark schemes?|marks?|o\.?w\.?l\.?s?|practical|grades?)\b",
    re.IGNORECASE,
)
_SCOPE = re.compile(
    r"\b(topics?|subjects?|cover|covered|covers|include|includes|included|"
    r"curriculum|syllabus|course)\b",
    re.IGNORECASE,
)
_SELF = re.compile(r"^\s*(your|you|yourself|yourselves|my|me)\b", re.IGNORECASE)
_PERSON_CUE = re.compile(
    r"\b(professor|prof\.?|mr\.?|mrs\.?|ms\.?|miss|sir|madam|lord|lady|"
    r"harry|hermione|ron|dumbledore|snape|hagrid|lupin|sirius|voldemort|"
    r"draco|mcgonagall|crane|raman)\b",
    re.IGNORECASE,
)
_PLACE_CUE = re.compile(
    r"\b(hogwarts|hogsmeade|diagon alley|azkaban|gryffindor|slytherin|"
    r"ravenclaw|hufflepuff|durmstrang|beauxbatons|ministry|the burrow|"
    r"privet drive|knockturn alley|forbidden forest)\b",
    re.IGNORECASE,
)
_COMPOUND = re.compile(
    r"\s+and\s+(?:what|who|how|why|where|when|which|does|did|is|are|can|"
    r"could|should|would)\b.*$",
    re.IGNORECASE,
)


def memory_saver() -> MemorySaver:
    """The process-local checkpointer, with the state chunk type allowlisted.

    The graph stores retrieved ``Chunk`` objects in state. LangGraph's default
    serializer warns about unregistered types and will block them in a future
    release, so name the one type the state carries.
    """
    return MemorySaver(
        serde=JsonPlusSerializer(allowed_msgpack_modules=[("app.schemas", "Chunk")])
    )


@dataclass(frozen=True)
class Entity:
    """A named entity and the pronoun class it can satisfy."""

    text: str
    kind: EntityKind


@dataclass(frozen=True)
class Resolution:
    """The standalone query, an optional forced mode and an authority hint."""

    standalone: str
    forced_mode: str | None = None
    preferred_mode: str | None = None


def _infer_kind(text: str, default: EntityKind) -> EntityKind:
    if _PERSON_CUE.search(text):
        return "person"
    if _PLACE_CUE.search(text):
        return "place"
    return default


def extract_entity(question: str) -> Entity | None:
    """The named entity a follow-up pronoun is likely to refer to."""
    for pattern, kind in (
        (_WHO, "person"),
        (_TELL, "thing"),
        (_WHERE, "place"),
        (_GO, "place"),
    ):
        match = pattern.match(question)
        if match:
            text = _COMPOUND.sub("", match.group(1)).strip()
            if _SELF.match(text):
                return None
            return Entity(text, _infer_kind(text, kind))
    match = _WHAT.match(question)
    if match:
        text = _COMPOUND.sub("", match.group(1)).strip()
        if _SELF.match(text):
            return None
        return Entity(text, _infer_kind(text, "thing"))
    return None


def _recent_entity(
    messages: list[dict[str, str]], summary: str, kind: EntityKind | None
) -> str | None:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        entity = extract_entity(message.get("content", ""))
        if entity and (kind is None or entity.kind == kind):
            return entity.text
    for segment in reversed(summary.split("Earlier:")):
        entity = extract_entity(segment.strip())
        if entity and (kind is None or entity.kind == kind):
            return entity.text
    return None


def resolve_followup(
    question: str,
    *,
    messages: list[dict[str, str]] | None = None,
    summary: str = "",
    last_entity: str | None = None,
    last_person: str | None = None,
    last_place: str | None = None,
    last_mode: str | None = None,
    pending_clarify: bool = False,
    subject: str = "dada",
) -> Resolution:
    """Resolve a follow-up against the thread state without changing authority."""
    text = question.strip()
    if pending_clarify:
        if _PRACTICE.search(text):
            return Resolution(text, forced_mode="practice")
        if _NEW_QUESTION.match(text) or "?" in text:
            pass
        elif _EXAM.search(text):
            return Resolution(text, forced_mode="policy")
        elif _SCOPE.search(text):
            name = SUBJECT_NAMES.get(subject, subject)
            return Resolution(f"What does {name} cover?")
        else:
            return Resolution(text, forced_mode="clarify")

    messages = messages or []
    person = last_person or _recent_entity(messages, summary, "person")
    place = last_place or _recent_entity(messages, summary, "place")
    any_entity = (
        last_entity
        or person
        or place
        or _recent_entity(messages, summary, None)
    )
    lesson_hint = "lesson" if last_mode == "lesson" else None
    if _PERSON_PRONOUN.search(text) and person:
        return Resolution(
            _PERSON_PRONOUN.sub(lambda _: person, text, count=1),
            preferred_mode=lesson_hint,
        )
    if _THEY.search(text) and any_entity:
        return Resolution(
            _THEY.sub(lambda _: any_entity, text, count=1),
            preferred_mode=lesson_hint,
        )
    if _THERE.search(text) and place and not _THERE_QUESTION.search(text):
        return Resolution(
            _THERE.sub(lambda _: place, text, count=1),
            preferred_mode=lesson_hint,
        )

    if last_mode is not None:
        match = _WHAT_ABOUT.match(text)
        if match:
            target = match.group(1).strip()
            if last_mode in {"lesson", "answer"}:
                return Resolution(
                    f"Tell me about {target}.",
                    preferred_mode="lesson" if last_mode == "lesson" else None,
                )
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
    "Entity",
    "Resolution",
    "TOKEN_BUDGET",
    "WINDOW_MESSAGES",
    "context_chars",
    "extract_entity",
    "memory_saver",
    "resolve_followup",
    "trim_history",
]
