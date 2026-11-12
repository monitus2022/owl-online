"""Lesson and multi-turn RAG fixtures: ids, scopes and expected routes.

The fixtures are built from the published packs by
`scripts/build_rag_fixtures.py`. They store concept titles, material ids and
source-ref structure only; no material prose or corpus text is committed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.knowledge.taxonomy import SUBJECT_KEYS

LESSON_SLICES = frozenset(
    {"in_pack", "paraphrase", "multi_concept", "mixed", "off_pack", "abstain"}
)
MULTITURN_SLICES = frozenset(
    {
        "same_subject_comparison",
        "third_topic",
        "pronoun",
        "implicit_referent",
        "correction",
        "off_topic",
        "cross_subject",
    }
)
SCOPES = frozenset({"in_pack", "mixed", "off_pack", "abstained"})
CITATIONS = frozenset({"material", "book", "both", "either", "none"})
MODES = frozenset(
    {
        "answer",
        "practice",
        "feedback",
        "lesson",
        "meta",
        "personal",
        "fact",
        "clarify",
        "policy",
        "abstain",
        "referral",
    }
)
REQUEST_MODES = frozenset({"auto", "answer", "practice", "feedback", "lesson"})


@dataclass(frozen=True)
class GroupExpectation:
    """One concept group and the materials that can satisfy it.

    A concept may have several materials. The citation check requires at least
    one material from each expected group, not every material, so a complete
    answer is not penalised for citing one of two notes on the same concept.
    """

    title: str
    material_ids: tuple[str, ...]


@dataclass(frozen=True)
class LessonItem:
    """One lesson question and the material ids that should ground it."""

    item_id: str
    subject: str
    question: str
    slice_name: str
    answerable: bool
    expected_scope: str
    citation: str
    expected_material_ids: tuple[str, ...]
    expected_source_refs: tuple[dict[str, object], ...]
    expected_groups: tuple[GroupExpectation, ...] = ()
    expected_chunk_ids: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Turn:
    """One turn in a multi-turn conversation."""

    question: str
    mode: str
    expected_standalone: str
    expected_mode: str
    expected_material_ids: tuple[str, ...] = ()
    expected_groups: tuple[GroupExpectation, ...] = ()
    expected_abstained: bool | None = False
    expected_referral_subject: str | None = None
    expected_referral_concept: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Conversation:
    """One multi-turn conversation."""

    conversation_id: str
    subject: str
    slice_name: str
    turns: tuple[Turn, ...]
    note: str = ""


def _require_str(record: dict[str, object], key: str, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: missing or empty {key!r}")
    return value.strip()


def _optional_str(record: dict[str, object], key: str, where: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{where}: {key!r} must be a string or null")
    return value.strip() or None


def _string_tuple(record: dict[str, object], key: str, where: str) -> tuple[str, ...]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{where}: {key!r} must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def _source_refs(record: dict[str, object], where: str) -> tuple[dict[str, object], ...]:
    value = record.get("expected_source_refs", [])
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected_source_refs must be a list")
    refs: list[dict[str, object]] = []
    for index, ref in enumerate(value):
        if not isinstance(ref, dict):
            raise ValueError(f"{where}: source ref {index} must be an object")
        chunk_id = _require_str(ref, "chunk_id", f"{where}: source ref {index}")
        book = ref.get("book")
        chapter = ref.get("chapter")
        if not isinstance(book, int) or not isinstance(chapter, int):
            raise ValueError(f"{where}: source ref {index} needs integer book and chapter")
        refs.append({"chunk_id": chunk_id, "book": book, "chapter": chapter})
    return tuple(refs)


def _groups(record: dict[str, object], where: str) -> tuple[GroupExpectation, ...]:
    value = record.get("expected_groups", [])
    if not isinstance(value, list):
        raise ValueError(f"{where}: expected_groups must be a list")
    groups: list[GroupExpectation] = []
    for index, group in enumerate(value):
        if not isinstance(group, dict):
            raise ValueError(f"{where}: group {index} must be an object")
        title = _require_str(group, "title", f"{where}: group {index}")
        material_ids = _string_tuple(group, "material_ids", f"{where}: group {index}")
        if not material_ids:
            raise ValueError(f"{where}: group {index} needs material_ids")
        groups.append(GroupExpectation(title, material_ids))
    return tuple(groups)


def parse_lesson_item(record: dict[str, object], where: str) -> LessonItem:
    item_id = _require_str(record, "id", where)
    subject = _require_str(record, "subject", where)
    if subject not in SUBJECT_KEYS:
        raise ValueError(f"{where}: unknown subject {subject!r}")
    question = _require_str(record, "question", where)
    slice_name = _require_str(record, "slice", where)
    if slice_name not in LESSON_SLICES:
        raise ValueError(f"{where}: unknown lesson slice {slice_name!r}")
    answerable = record.get("answerable")
    if not isinstance(answerable, bool):
        raise ValueError(f"{where}: answerable must be a boolean")
    expected_scope = _require_str(record, "expected_scope", where)
    if expected_scope not in SCOPES:
        raise ValueError(f"{where}: unknown scope {expected_scope!r}")
    citation = _require_str(record, "citation", where)
    if citation not in CITATIONS:
        raise ValueError(f"{where}: unknown citation mode {citation!r}")
    material_ids = _string_tuple(record, "expected_material_ids", where)
    chunk_ids = _string_tuple(record, "expected_chunk_ids", where)
    if answerable and not (material_ids or chunk_ids):
        raise ValueError(f"{where}: an answerable item needs expected material or chunk ids")
    if not answerable and (material_ids or chunk_ids):
        raise ValueError(f"{where}: an unanswerable item must not expect evidence ids")
    note = _optional_str(record, "note", where) or ""
    return LessonItem(
        item_id=item_id,
        subject=subject,
        question=question,
        slice_name=slice_name,
        answerable=answerable,
        expected_scope=expected_scope,
        citation=citation,
        expected_material_ids=material_ids,
        expected_source_refs=_source_refs(record, where),
        expected_groups=_groups(record, where),
        expected_chunk_ids=chunk_ids,
        note=note,
    )


def parse_turn(record: dict[str, object], where: str) -> Turn:
    question = _require_str(record, "question", where)
    mode = _require_str(record, "mode", where)
    if mode not in REQUEST_MODES:
        raise ValueError(f"{where}: unknown request mode {mode!r}")
    expected_standalone = _require_str(record, "expected_standalone", where)
    expected_mode = _require_str(record, "expected_mode", where)
    if expected_mode not in MODES:
        raise ValueError(f"{where}: unknown expected mode {expected_mode!r}")
    material_ids = _string_tuple(record, "expected_material_ids", where)
    expected_abstained = record.get("expected_abstained", False)
    if expected_abstained is not None and not isinstance(expected_abstained, bool):
        raise ValueError(f"{where}: expected_abstained must be boolean or null")
    referral_subject = _optional_str(record, "expected_referral_subject", where)
    if referral_subject is not None and referral_subject not in SUBJECT_KEYS:
        raise ValueError(f"{where}: unknown referral subject {referral_subject!r}")
    referral_concept = _optional_str(record, "expected_referral_concept", where)
    if (referral_subject is None) != (referral_concept is None):
        raise ValueError(f"{where}: referral subject and concept must be set together")
    note = _optional_str(record, "note", where) or ""
    return Turn(
        question=question,
        mode=mode,
        expected_standalone=expected_standalone,
        expected_mode=expected_mode,
        expected_material_ids=material_ids,
        expected_groups=_groups(record, where),
        expected_abstained=expected_abstained,
        expected_referral_subject=referral_subject,
        expected_referral_concept=referral_concept,
        note=note,
    )


def parse_conversation(record: dict[str, object], where: str) -> Conversation:
    conversation_id = _require_str(record, "id", where)
    subject = _require_str(record, "subject", where)
    if subject not in SUBJECT_KEYS:
        raise ValueError(f"{where}: unknown subject {subject!r}")
    slice_name = _require_str(record, "slice", where)
    if slice_name not in MULTITURN_SLICES:
        raise ValueError(f"{where}: unknown multi-turn slice {slice_name!r}")
    raw_turns = record.get("turns")
    if not isinstance(raw_turns, list) or not raw_turns:
        raise ValueError(f"{where}: turns must be a non-empty list")
    turns = tuple(
        parse_turn(turn, f"{where}: turn {index}")
        for index, turn in enumerate(raw_turns, 1)
        if isinstance(turn, dict)
    )
    if len(turns) != len(raw_turns):
        raise ValueError(f"{where}: every turn must be an object")
    note = _optional_str(record, "note", where) or ""
    return Conversation(
        conversation_id=conversation_id,
        subject=subject,
        slice_name=slice_name,
        turns=turns,
        note=note,
    )


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        rows.append(record)
    if not rows:
        raise ValueError(f"{path}: no records")
    return rows


def load_lesson_items(path: Path) -> list[LessonItem]:
    """Load the lesson fixture; duplicate ids fail loudly."""
    items: list[LessonItem] = []
    seen: set[str] = set()
    for line_number, record in enumerate(_load_jsonl(path), 1):
        item = parse_lesson_item(record, f"{path}:{line_number}")
        if item.item_id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate id {item.item_id!r}")
        seen.add(item.item_id)
        items.append(item)
    return items


def load_conversations(path: Path) -> list[Conversation]:
    """Load the multi-turn fixture; duplicate ids fail loudly."""
    conversations: list[Conversation] = []
    seen: set[str] = set()
    for line_number, record in enumerate(_load_jsonl(path), 1):
        conversation = parse_conversation(record, f"{path}:{line_number}")
        if conversation.conversation_id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate id {conversation.conversation_id!r}")
        seen.add(conversation.conversation_id)
        conversations.append(conversation)
    return conversations


__all__ = [
    "CITATIONS",
    "Conversation",
    "GroupExpectation",
    "LESSON_SLICES",
    "LessonItem",
    "MODES",
    "MULTITURN_SLICES",
    "REQUEST_MODES",
    "SCOPES",
    "Turn",
    "load_conversations",
    "load_lesson_items",
    "parse_conversation",
    "parse_lesson_item",
    "parse_turn",
]
