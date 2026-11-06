"""Persona card loader: the professor's voice, boundaries and scripted replies.

The card lives in `config/persona.toml`; the human copy is `docs/persona.md`.
This module is the single source of truth the prompts and the meta nodes read.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PERSONA_PATH = Path(__file__).resolve().parents[2] / "config" / "persona.toml"

META_TOPICS = (
    "identity",
    "scope",
    "exam",
    "syllabus",
    "grading",
    "school",
    "professor",
    "auror",
    "boundaries",
    "greeting",
)
REQUIRED_BOUNDARIES = ("facts", "advice", "canon", "exam")


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
    meta: dict[str, str]
    personal: str

    def answer_suffix(self) -> str:
        """The tone instruction appended to a grounded answer prompt.

        Deliberately omits the school and the lore: the answer prompt carries
        tone only. Naming the school here invites the model to substitute it for
        a place in the excerpts, which is a grounding error.
        """
        return (
            f"You are {self.address}, a {self.role}. "
            f"Speak in this register: {self.tone}. "
            f"{self.stance}. {self.pacing}. "
            "Use every name, place and title exactly as it appears in the "
            "excerpts; never rename or relocate it. "
            "Keep the citation and abstention rules above exactly. "
            f"{self.boundaries['facts']} {self.boundaries['advice']}"
        )

    def meta_response(self, topic: str) -> str | None:
        return self.meta.get(topic)

    def personal_response(self) -> str:
        return self.personal


def load_persona(path: Path = PERSONA_PATH) -> Persona:
    """Read and validate the persona card.

    A missing section or meta topic fails at startup: a half-loaded persona
    should not quietly answer in the wrong voice.
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    try:
        identity = data["identity"]
        register = data["register"]
        boundaries = data["boundaries"]
        meta = data["meta"]
        personal = data["personal"]
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

    meta_values = {
        topic: text(meta, topic, "meta") for topic in META_TOPICS
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
        personal=text(personal, "response", "personal"),
    )


PERSONA = load_persona()
