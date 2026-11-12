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

import json
import re
from dataclasses import dataclass
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from app.knowledge.taxonomy import SUBJECT_NAMES
from app.pipeline.generate.generate import sanitize_evidence

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
    r"\b(test me|quiz me|practice questions?)\b",
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
_SELF = re.compile(
    r"^\s*(?:yourself|yourselves|you|me|myself)\s*[?.!]*\s*$",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"^\s*(?:no[, ]+)?(?:i\s+meant|i\s+mean)\s*,?\s+(.+?)[?.!]*\s*$",
    re.IGNORECASE,
)
_ONE_REFERENT = re.compile(
    r"\b(defeat|beat|stop|counter|kill|fight|hurt|use|cast|pronounce|say|do)"
    r"\s+one\b",
    re.IGNORECASE,
)
_IT_REFERENT = re.compile(
    r"\b(defeat|beat|stop|counter|kill|fight|hurt|use|cast|pronounce|say|do|"
    r"of|for|with|to)\s+it\b",
    re.IGNORECASE,
)
_TELL_IT = re.compile(r"^\s*tell me about\s+it\s*[?.!]*$", re.IGNORECASE)
_ITS_REFERENT = re.compile(r"\bits\b", re.IGNORECASE)
_THAT_REFERENT = re.compile(
    r"^\s*(?:what(?:'s| is)|tell me about)\s+that\s*[?.!]*$",
    re.IGNORECASE,
)
_COUNTER_REFERENT = re.compile(
    r"^\s*(?:and\s+)?(?:what about\s+)?the counter\??\s*$",
    re.IGNORECASE,
)
_WHY_ALONE = re.compile(r"^\s*why\s*[?.!]*$", re.IGNORECASE)
_HOW_ALONE = re.compile(r"^\s*how\s*[?.!]*$", re.IGNORECASE)
_IMPLICIT_TARGETS = frozenset(
    {"it", "its", "one", "that", "the same", "him", "her", "them", "they"}
)
_CITATION = re.compile(
    r"\[[^\]]*(?:b\d+-c\d+-\d+|lore:|mat:|policy:|persona:|lesson:)[^\]]*\]",
    re.IGNORECASE,
)
_PERSON_ROLE = re.compile(
    r"\b(professor|prof\.?|mr\.?|mrs\.?|ms\.?|miss|sir|madam|lord|lady|"
    r"head of|headmaster|headmistress|minister for magic|minister|teacher|"
    r"student|auror|seeker|keeper|chaser|beater|prefect|ghost|founder|"
    r"captain|official)\b",
    re.IGNORECASE,
)
_PERSON_NAME = re.compile(
    r"\b(Harry|Hermione|Ron|Neville|Luna|Ginny|Cedric|Tonks|Moody|Umbridge|"
    r"Fred|George|Percy|Bill|Charlie|Fleur|Krum|Cho|Dean|Seamus|Lavender|"
    r"Parvati|Padma|Dumbledore|Snape|Hagrid|Lupin|Sirius|Voldemort|Draco|"
    r"McGonagall|Crane|Raman|Bellatrix|Lucius|Narcissa|Pettigrew)\b"
)
_THING_CUE = re.compile(
    r"\b(spell|charm|curse|jinx|hex|potion|wand|broom|uniform|book|creature|"
    r"beast|plant|herb|ingredient|cauldron|cloak|map|stone|cup|diary|locket|"
    r"snake|dragon|boggart|dementor|patronus|expelliarmus|avifors|lumos|"
    r"owl|cat|rat|toad|phoenix|thestral|hippogriff|unicorn|mermaid|vampire|"
    r"troll|dwarf|elf|house-elf|goblin|centaur|giant|werewolf|animagus)\b",
    re.IGNORECASE,
)
_PLACE_CUE = re.compile(
    r"\b(hogwarts|hogsmeade|diagon alley|azkaban|gryffindor|slytherin|"
    r"ravenclaw|hufflepuff|durmstrang|beauxbatons|ministry|the burrow|"
    r"privet drive|knockturn alley|forbidden forest|school|library|"
    r"great hall|common room|classroom|castle|grounds|dormitory|tower|"
    r"dungeon|greenhouse|quidditch pitch|hospital wing)\b",
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
    return MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=[("app.schemas", "Chunk")]))


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
    rule: str | None = None
    entity: str | None = None


def _infer_kind(text: str, default: EntityKind) -> EntityKind:
    if _PERSON_ROLE.search(text) or _PERSON_NAME.search(text):
        return "person"
    if _THING_CUE.search(text):
        return "thing"
    if _PLACE_CUE.search(text):
        return "place"
    return default


def _is_proper(entity: str, kind: EntityKind) -> bool:
    """A person, place or spell name keeps its name and takes no article."""
    if kind in {"person", "place"}:
        return True
    return " " not in entity and entity[:1].isupper() and entity.lower().endswith(("us", "um", "o"))


def _is_referent_phrase(text: str) -> bool:
    """True for a noun phrase that is only a referent, not a new topic."""
    lowered = text.lower().strip()
    if lowered in _IMPLICIT_TARGETS:
        return True
    return any(
        lowered.startswith(f"{token} ") or lowered.startswith(f"{token}'s ")
        for token in _IMPLICIT_TARGETS
    )


def _indefinite(entity: str, kind: EntityKind) -> str:
    """An article for an object follow-up; a proper name keeps its name."""
    if _is_proper(entity, kind):
        return entity
    lowered = entity.lower()
    if lowered.startswith(("a ", "an ", "the ")):
        return entity
    if lowered.startswith(("uni", "use", "one", "eu")):
        return f"a {entity}"
    return f"an {entity}" if entity[:1].lower() in "aeiou" else f"a {entity}"


def _definite(entity: str, kind: EntityKind) -> str:
    """A definite phrase for an object follow-up; a proper name stays as-is."""
    if _is_proper(entity, kind):
        return entity
    lowered = entity.lower()
    if lowered.startswith("the "):
        return entity
    if lowered.startswith(("a ", "an ")):
        return f"the {entity.split(' ', 1)[1]}"
    return f"the {entity}"


def _last_kind(
    last_entity: str | None,
    last_person: str | None,
    last_place: str | None,
) -> EntityKind | None:
    if last_entity and last_entity == last_person:
        return "person"
    if last_entity and last_entity == last_place:
        return "place"
    return "thing" if last_entity else None


def _implicit_resolution(
    text: str,
    entity: str,
    kind: EntityKind,
    lesson_hint: str | None,
) -> Resolution | None:
    """Resolve a short referent question against the last entity."""
    if _COUNTER_REFERENT.match(text):
        return Resolution(
            f"What is the counter to {_definite(entity, kind)}?",
            preferred_mode=lesson_hint,
            rule="counter",
            entity=entity,
        )
    if _THAT_REFERENT.match(text):
        return Resolution(
            f"What is {_definite(entity, kind)}?",
            preferred_mode=lesson_hint,
            rule="implicit_that",
            entity=entity,
        )
    if _WHY_ALONE.match(text):
        return Resolution(
            f"Why does that matter for {_definite(entity, kind)}?",
            preferred_mode=lesson_hint,
            rule="why",
            entity=entity,
        )
    if _HOW_ALONE.match(text):
        return Resolution(
            f"How does that work for {_definite(entity, kind)}?",
            preferred_mode=lesson_hint,
            rule="how",
            entity=entity,
        )
    if _TELL_IT.match(text):
        return Resolution(
            f"Tell me about {entity}.",
            preferred_mode=lesson_hint,
            rule="implicit_tell",
            entity=entity,
        )
    if _ONE_REFERENT.search(text):
        return Resolution(
            _ONE_REFERENT.sub(
                lambda match: f"{match.group(1)} {_indefinite(entity, kind)}",
                text,
                count=1,
            ),
            preferred_mode=lesson_hint,
            rule="implicit_one",
            entity=entity,
        )
    if _IT_REFERENT.search(text):
        return Resolution(
            _IT_REFERENT.sub(
                lambda match: f"{match.group(1)} {_definite(entity, kind)}",
                text,
                count=1,
            ),
            preferred_mode=lesson_hint,
            rule="implicit_it",
            entity=entity,
        )
    if _ITS_REFERENT.search(text):
        base = _definite(entity, kind)
        possessive = base if base.endswith("'s") else f"{base}'s"
        return Resolution(
            _ITS_REFERENT.sub(lambda _: possessive, text, count=1),
            preferred_mode=lesson_hint,
            rule="implicit_its",
            entity=entity,
        )
    return None


def extract_entity(question: str) -> Entity | None:
    """The named entity a follow-up pronoun is likely to refer to."""
    for pattern, kind in (
        (_WHO, "person"),
        (_TELL, "thing"),
        (_WHERE, "place"),
        (_GO, "place"),
        (_WHAT_ABOUT, "thing"),
    ):
        match = pattern.match(question)
        if match:
            text = _COMPOUND.sub("", match.group(1)).strip()
            if _SELF.match(text):
                return None
            # "Who is ..." is a person question even when the target names a
            # house or school; the other patterns infer from the target.
            inferred = kind if pattern is _WHO else _infer_kind(text, kind)
            return Entity(text, inferred)
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
    any_entity = last_entity or person or place or _recent_entity(messages, summary, None)
    lesson_hint = "lesson" if last_mode == "lesson" else None
    last_kind = _last_kind(last_entity, last_person, last_place)
    if last_entity:
        correction = _CORRECTION.match(text)
        if correction:
            target = correction.group(1).strip()
            if _NEW_QUESTION.match(target):
                # "I mean, what is a Patronus?" is a new question, not a
                # correction to the old topic.
                text = target + ("?" if text.rstrip().endswith("?") else "")
            else:
                if target.lower() in {"him", "her", "he", "she"} and person:
                    target = person
                elif target.lower() in {"them", "they"} and any_entity:
                    target = any_entity
                elif target.lower() in _IMPLICIT_TARGETS:
                    target = last_entity
                if target and not _SELF.match(target) and len(target.split()) <= 6:
                    return Resolution(
                        f"Tell me about {target}.",
                        preferred_mode=lesson_hint,
                        rule="correction",
                        entity=target,
                    )
        own = extract_entity(text)
        implicit_ok = not (
            own is not None
            and own.text.lower() != last_entity.lower()
            and not _is_referent_phrase(own.text)
        )
        if (
            implicit_ok
            and not _EXAM.search(text)
            and not _SCOPE.search(text)
            and not _SELF.match(text)
        ):
            implicit = _implicit_resolution(text, last_entity, last_kind or "thing", lesson_hint)
            if implicit is not None:
                return implicit
    if _PERSON_PRONOUN.search(text) and person:
        return Resolution(
            _PERSON_PRONOUN.sub(lambda _: person, text, count=1),
            preferred_mode=lesson_hint,
            rule="person_pronoun",
            entity=person,
        )
    if _THEY.search(text) and any_entity:
        return Resolution(
            _THEY.sub(lambda _: any_entity, text, count=1),
            preferred_mode=lesson_hint,
            rule="they",
            entity=any_entity,
        )
    if _THERE.search(text) and place and not _THERE_QUESTION.search(text):
        return Resolution(
            _THERE.sub(lambda _: place, text, count=1),
            preferred_mode=lesson_hint,
            rule="there",
            entity=place,
        )

    if last_mode is not None:
        match = _WHAT_ABOUT.match(text)
        if match:
            target = match.group(1).strip()
            if target.lower() in _IMPLICIT_TARGETS and last_entity:
                target = last_entity
            hint = "lesson" if last_mode == "lesson" else None
            target_kind = _infer_kind(target, "thing")
            if (
                last_mode in {"lesson", "answer"}
                and last_entity
                and last_entity.lower() != target.lower()
                and last_kind == target_kind
                and not _EXAM.search(target)
                and not _SCOPE.search(target)
                and not _SELF.match(target)
            ):
                # Retrieve both topics; the prompt keeps the student's wording
                # and the conversation block, so the model decides whether to
                # compare them.
                return Resolution(
                    f"Compare {last_entity} with {target}.",
                    preferred_mode=hint,
                    rule="compare",
                    entity=target,
                )
            return Resolution(
                f"Tell me about {target}.",
                preferred_mode=hint,
                rule="what_about",
                entity=target,
            )

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


def render_context(
    messages: list[dict[str, str]],
    summary: str,
    *,
    token_budget: int = TOKEN_BUDGET,
) -> str:
    """Render the bounded conversation block sent with a threaded prompt."""

    def clean(text: str) -> str:
        cleaned, _ = sanitize_evidence(text)
        return _CITATION.sub("", cleaned).strip()

    parts: list[str] = []
    summary_text = clean(summary)
    if summary_text:
        parts.append(json.dumps({"role": "summary", "content": summary_text}, ensure_ascii=False))
    for message in messages:
        content = clean(message.get("content", ""))
        if not content:
            continue
        role = "student" if message.get("role") == "user" else "professor"
        parts.append(json.dumps({"role": role, "content": content}, ensure_ascii=False))
    limit = max(1, token_budget) * _CHARS_PER_TOKEN
    while len(parts) > 1 and sum(len(part) + 1 for part in parts) > limit:
        parts.pop(0)
    if parts and len(parts[0]) > limit:
        parts[0] = parts[0][:limit]
    return "\n".join(parts).strip()


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
    "render_context",
    "resolve_followup",
    "trim_history",
]
