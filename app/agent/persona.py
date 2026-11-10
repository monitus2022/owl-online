"""Persona card loader: the professor's voice, boundaries and scripted replies.

The DADA card lives in `config/persona.toml`; the other four cards live in
`config/personas/<subject>.toml` and are merged over `config/personas/spine.toml`.
The human copy is `docs/persona.md`. This module is the single source of truth
the prompts and the meta nodes read.
"""

from __future__ import annotations

import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PERSONA_PATH = REPO_ROOT / "config" / "persona.toml"
PERSONAS_DIR = REPO_ROOT / "config" / "personas"
SPINE_PATH = PERSONAS_DIR / "spine.toml"
PERSONA_SUBJECTS = ("dada", "potions", "transfiguration", "charms", "herbology")

META_TOPICS = (
    "identity",
    "scope",
    "exam",
    "syllabus",
    "subject",
    "grading",
    "school",
    "professor",
    "auror",
    "boundaries",
    "greeting",
)
REQUIRED_BOUNDARIES = ("facts", "advice", "canon", "exam", "record")


@dataclass(frozen=True)
class Persona:
    """A reviewed persona card."""

    name: str
    address: str
    role: str
    school: str
    subject: str
    tone: str
    pacing: str
    stance: str
    boundaries: dict[str, str]
    meta: dict[str, tuple[str, ...]]
    personal: tuple[str, ...]
    abstain: tuple[str, ...]

    @staticmethod
    def _pick(variants: tuple[str, ...], choice: int | None) -> str:
        """One reviewed variant.

        Selection is random per request so a repeated meta, personal or
        abstention message does not repeat the same line. Tests pass `choice`
        to make the result reproducible.
        """
        if choice is None:
            return random.choice(variants)
        return variants[choice % len(variants)]

    def answer_suffix(self) -> str:
        """The tone instruction appended to a grounded answer prompt.

        Deliberately omits the school and the lore: the answer prompt carries
        tone, the facts, advice and record boundaries, and the Ashcombe exam
        boundary. Naming the school here invites the model to substitute it for a
        place in the excerpts, which is a grounding error.
        """
        return (
            f"You are {self.address}, a {self.role}. "
            f"Speak in this register: {self.tone}. "
            f"{self.stance}. {self.pacing}. "
            "Use every name, place and title exactly as it appears in the "
            "excerpts; never rename or relocate it. "
            "Keep the citation and abstention rules above exactly. "
            f"{self.boundaries['facts']} {self.boundaries['advice']} "
            f"{self.boundaries['record']} {self.boundaries['exam']}"
        )

    def meta_response(self, topic: str, *, choice: int | None = None) -> str | None:
        variants = self.meta.get(topic)
        if not variants:
            return None
        return self._pick(variants, choice)

    def meta_variants(self, topic: str) -> tuple[str, ...]:
        return self.meta.get(topic, ())

    def personal_response(self, *, choice: int | None = None) -> str:
        return self._pick(self.personal, choice)

    def personal_variants(self) -> tuple[str, ...]:
        return self.personal

    def abstain_response(self, *, choice: int | None = None) -> str:
        return self._pick(self.abstain, choice)

    def abstain_variants(self) -> tuple[str, ...]:
        return self.abstain


def _variants(value: object, where: str) -> tuple[str, ...]:
    """Read a reviewed string or a list of reviewed strings from the card.

    A variant bank keeps the facts identical and only changes the phrasing, so
    every entry is validated here rather than at request time.
    """
    if isinstance(value, str):
        raw: list[object] = [value]
    elif isinstance(value, list):
        raw = value
    else:
        raise ValueError(f"persona card has an invalid {where}")
    if not raw:
        raise ValueError(f"persona card has an empty {where}")
    texts: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError(f"persona card has an invalid {where}")
        text = item.strip()
        if not text:
            raise ValueError(f"persona card has an empty {where}")
        texts.append(text)
    if len(set(texts)) != len(texts):
        raise ValueError(f"persona card has a duplicate variant in {where}")
    return tuple(texts)


def _persona_from_data(data: dict[str, object]) -> Persona:
    """Validate one card, after the shared spine has been merged in."""
    try:
        identity = data["identity"]
        register = data["register"]
        boundaries = data["boundaries"]
        meta = data["meta"]
        personal = data["personal"]
        abstain = data["abstain"]
    except KeyError as error:
        raise ValueError(f"persona card is missing section {error}") from error
    missing = [topic for topic in META_TOPICS if topic not in meta]
    if missing:
        raise ValueError(f"persona card is missing meta topics: {missing}")
    missing_boundaries = [key for key in REQUIRED_BOUNDARIES if key not in boundaries]
    if missing_boundaries:
        raise ValueError(
            f"persona card is missing boundaries: {missing_boundaries}"
        )

    def text(section: dict[str, object], key: str, where: str) -> str:
        if key not in section:
            raise ValueError(f"persona card is missing {where}.{key}")
        value = str(section[key]).strip()
        if not value:
            raise ValueError(f"persona card has an empty {where}.{key}")
        return value

    def variants(
        section: dict[str, object], key: str, where: str
    ) -> tuple[str, ...]:
        if key not in section:
            raise ValueError(f"persona card is missing {where}.{key}")
        return _variants(section[key], f"{where}.{key}")

    meta_values = {
        topic: variants(meta, topic, "meta") for topic in META_TOPICS
    }
    return Persona(
        name=text(identity, "name", "identity"),
        address=text(identity, "address", "identity"),
        role=text(identity, "role", "identity"),
        school=text(identity, "school", "identity"),
        subject=text(identity, "subject", "identity"),
        tone=text(register, "tone", "register"),
        pacing=text(register, "pacing", "register"),
        stance=text(register, "stance", "register"),
        boundaries={
            str(key): text(boundaries, str(key), "boundaries")
            for key in REQUIRED_BOUNDARIES
        },
        meta=meta_values,
        personal=variants(personal, "response", "personal"),
        abstain=variants(abstain, "response", "abstain"),
    )


def load_persona(path: Path = PERSONA_PATH) -> Persona:
    """Read and validate one standalone card.

    A missing section or meta topic fails at startup: a half-loaded persona
    should not quietly answer in the wrong voice.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return _persona_from_data(data)


def _deep_merge(
    base: dict[str, object], override: dict[str, object]
) -> dict[str, object]:
    """Merge nested TOML tables; lists and scalars replace the spine value."""
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def load_personas() -> dict[str, Persona]:
    """Load the DADA seed and the four cards merged over the shared spine."""
    spine = tomllib.loads(SPINE_PATH.read_text(encoding="utf-8"))
    personas = {"dada": load_persona(PERSONA_PATH)}
    for subject in PERSONA_SUBJECTS[1:]:
        path = PERSONAS_DIR / f"{subject}.toml"
        card = tomllib.loads(path.read_text(encoding="utf-8"))
        personas[subject] = _persona_from_data(_deep_merge(spine, card))
    return personas


PERSONAS = load_personas()
PERSONA = PERSONAS["dada"]


def for_subject(subject: str) -> Persona:
    """The reviewed card for one subject key."""
    try:
        return PERSONAS[subject]
    except KeyError as error:
        raise KeyError(f"no persona card for subject {subject!r}") from error
