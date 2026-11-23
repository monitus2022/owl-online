"""Offline persona authoring: a brief, a draft, validators and provenance.

The five live cards were written by hand. This module makes the next card a
content task: a human writes a brief with the non-negotiable facts and voice
direction, a pinned prompt drafts the copy, deterministic validators and the
app's own persona loader check the merged card, and a human reviews it before
anything is published.

No runtime model call. The generator writes a draft; `publish` is the only
path that writes a live card, and only with a reviewer name.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from string import Formatter

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agent.persona import (
    META_TOPICS,
    PERSONAS_DIR,
    SPINE_PATH,
    load_persona_merged,
)
from app.knowledge.taxonomy import SUBJECT_KEYS, known_subject
from app.providers.contracts import Llm

AUTHORING_PROMPT_VERSION = "authoring-v2"

# The shared meta topics stay in the spine; a draft may override only the
# subject-specific ones. The refusals and school copy are not generated.
GENERATED_META_TOPICS = (
    "identity",
    "scope",
    "subject",
    "professor",
    "boundaries",
    "greeting",
)

MIN_VARIANTS = 3
MAX_VARIANTS = 5
MIN_VARIANT_CHARS = 10
MAX_VARIANT_CHARS = 500

# Canon names must not become the professor. Unambiguous names are checked
# anywhere; common-word surnames (Sprout, Vector, Riddle, Moody) need a title
# or a name field, so "the seedlings sprout" and "vector analysis" pass.
CANON_UNAMBIGUOUS = (
    "Dumbledore",
    "McGonagall",
    "Snape",
    "Flitwick",
    "Hagrid",
    "Lupin",
    "Umbridge",
    "Slughorn",
    "Lockhart",
    "Quirrell",
    "Trelawney",
    "Binns",
    "Burbage",
    "Sinistra",
    "Hooch",
    "Pomfrey",
    "Filch",
    "Pince",
    "Kettleburn",
    "Grubbly-Plank",
    "Firenze",
    "Carrow",
    "Crouch",
    "Voldemort",
    "Bellatrix",
    "Albus",
    "Severus",
    "Minerva",
    "Pomona",
    "Filius",
    "Horace",
    "Sybill",
    "Rubeus",
    "Remus",
    "Alastor",
    "Dolores",
    "Gilderoy",
    "Quirinus",
    "Cuthbert",
)
CANON_AMBIGUOUS = ("Sprout", "Vector", "Riddle", "Moody")
CANON_ALL = CANON_UNAMBIGUOUS + CANON_AMBIGUOUS
_CANON_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in CANON_UNAMBIGUOUS) + r")\b"
)
_CANON_TITLE_RE = re.compile(
    r"\b(?:Professor|Prof\.?)\s+(?:"
    + "|".join(re.escape(name) for name in CANON_ALL)
    + r")\b",
    re.IGNORECASE,
)
_CANON_NAME_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(name) for name in CANON_ALL) + r")\b",
    re.IGNORECASE,
)


def _canon_prose(text: str) -> bool:
    """A canon name in generated prose, with the common-word guard."""
    return bool(_CANON_RE.search(text) or _CANON_TITLE_RE.search(text))


def _canon_name(text: str) -> bool:
    """A canon name in a name/address field, title or not."""
    return bool(_CANON_NAME_RE.search(text))


def _content_problems(where: str, text: str) -> list[str]:
    """Placeholder, HTML, URL and model/provider wording checks."""
    problems: list[str] = []
    lowered = text.lower()
    for phrase in _BANNED_PHRASES:
        if phrase in lowered:
            problems.append(f"{where} mentions {phrase!r}")
    if _PLACEHOLDER.search(text):
        problems.append(f"{where} contains a placeholder")
    if _HTML_TAG.search(text):
        problems.append(f"{where} contains HTML")
    if _URL.search(text):
        problems.append(f"{where} contains a URL")
    return problems


CARD_SECTIONS = frozenset(
    {"identity", "register", "meta", "personal", "abstain", "facts", "templates"}
)
CARD_IDENTITY_KEYS = frozenset({"name", "address", "role", "subject"})
CARD_META_KEYS = frozenset(GENERATED_META_TOPICS)
SPINE_SHARED_META = frozenset(META_TOPICS) - CARD_META_KEYS
# The live cards override their own professor background; the shared school
# facts and the common education facts stay fixed.
CARD_OVERRIDABLE_SPINE_FACTS = frozenset({"professor.background"})

_BANNED_PHRASES = (
    "as an ai",
    "language model",
    "chatgpt",
    "openai",
    "anthropic",
    "claude",
    "gemini",
    "large language",
    "system prompt",
)

_PLACEHOLDER = re.compile(r"\{\{|\}\}|TODO|\[insert|\[placeholder", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")
_URL = re.compile(r"https?://", re.IGNORECASE)


class PersonaAuthoringError(ValueError):
    """A brief, draft or provenance file cannot be used."""


class PersonaBrief(BaseModel):
    """The human-authored seed for one persona card."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    subject: str
    name: str
    address: str
    role: str
    subject_title: str
    background: list[str] = Field(min_length=3, max_length=5)
    voice: str
    stance: str
    teaching: str
    relationships: list[str] = Field(default_factory=list)
    examples: list[str] = Field(min_length=2, max_length=6)
    avoid: list[str] = Field(default_factory=list)
    facts: dict[str, str]
    templates: dict[str, str]

    @field_validator("subject")
    @classmethod
    def _known_subject(cls, value: str) -> str:
        if value not in SUBJECT_KEYS:
            raise ValueError(f"unknown subject key {value!r}")
        return value

    @field_validator(
        "name", "address", "role", "subject_title", "voice", "stance", "teaching"
    )
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("brief fields must not be blank")
        return value.strip()

    @field_validator("background", "examples", "relationships", "avoid")
    @classmethod
    def _text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @model_validator(mode="after")
    def _consistent(self) -> PersonaBrief:
        known = known_subject(self.subject)
        if known is not None and known.name != self.subject_title:
            raise ValueError(
                f"subject_title {self.subject_title!r} does not match "
                f"{known.name!r}"
            )
        if (
            _canon_name(self.name)
            or _canon_name(self.address)
            or _canon_prose(self.role)
        ):
            raise ValueError(
                "the professor's identity must be original, not a canon name"
            )
        for label, values in (
            ("background", self.background),
            ("relationships", self.relationships),
            ("examples", self.examples),
            ("avoid", self.avoid),
        ):
            if any(_canon_prose(value) for value in values):
                raise ValueError(f"brief {label} must not name a canon figure")
        for label, value in (
            ("voice", self.voice),
            ("teaching", self.teaching),
            ("facts", " ".join(self.facts.values())),
            ("templates", " ".join(self.templates.values())),
        ):
            if _canon_prose(value):
                raise ValueError(f"brief {label} must not name a canon figure")
        for where, value in (
            ("name", self.name),
            ("address", self.address),
            ("role", self.role),
            *[(key, item) for key, item in self.facts.items()],
            *[(key, item) for key, item in self.templates.items()],
        ):
            problems = _content_problems(where, value)
            if problems:
                raise ValueError(problems[0])
        if not self.facts:
            raise ValueError("the brief needs fixed facts for the persona")
        if not self.templates:
            raise ValueError("the brief needs templates for the persona facts")
        if len(self.background) < 3:
            raise ValueError("the brief needs at least three background facts")
        if len(self.examples) < 2:
            raise ValueError("the brief needs at least two example lines")
        if any(not value.strip() for value in self.facts.values()):
            raise ValueError("brief facts must not be blank")
        if any(not value.strip() for value in self.templates.values()):
            raise ValueError("brief templates must not be blank")
        for key, template in self.templates.items():
            try:
                fields = {
                    field_name.split(".", 1)[0].split("[", 1)[0]
                    for _, field_name, _, _ in Formatter().parse(template)
                    if field_name is not None
                }
            except ValueError as error:
                raise ValueError(
                    f"template {key!r} is malformed: {error}"
                ) from error
            missing = fields - set(self.facts)
            if missing:
                raise ValueError(
                    f"template {key!r} references missing facts: {sorted(missing)}"
                )
        return self


class GeneratedPersona(BaseModel):
    """The JSON shape the authoring model must return."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    identity: dict[str, str]
    registration: dict[str, str] = Field(alias="register")
    meta: dict[str, list[str]]
    personal: list[str]
    abstain: list[str]
    facts: dict[str, str]
    templates: dict[str, str]

    @model_validator(mode="after")
    def _shape(self) -> GeneratedPersona:
        if set(self.identity) != {"name", "address", "role", "subject"}:
            raise ValueError(
                "identity must contain exactly name, address, role and subject"
            )
        if set(self.registration) != {"stance"}:
            raise ValueError("register must contain exactly stance")
        if set(self.meta) != set(GENERATED_META_TOPICS):
            raise ValueError(
                "meta must contain exactly "
                + ", ".join(GENERATED_META_TOPICS)
            )
        for where, values in (
            ("personal", self.personal),
            ("abstain", self.abstain),
        ):
            if not MIN_VARIANTS <= len(values) <= MAX_VARIANTS:
                raise ValueError(
                    f"{where} must have {MIN_VARIANTS}-{MAX_VARIANTS} variants"
                )
        for topic in GENERATED_META_TOPICS:
            if not MIN_VARIANTS <= len(self.meta[topic]) <= MAX_VARIANTS:
                raise ValueError(
                    f"meta.{topic} must have {MIN_VARIANTS}-{MAX_VARIANTS} variants"
                )
        return self


def load_brief(path: Path) -> PersonaBrief:
    """Read and validate one brief TOML file."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise PersonaAuthoringError(f"cannot read brief {path}: {error}") from error
    try:
        return PersonaBrief.model_validate(data)
    except Exception as error:
        raise PersonaAuthoringError(f"invalid brief {path}: {error}") from error


def _brief_json(brief: PersonaBrief) -> str:
    return json.dumps(brief.model_dump(), indent=2, ensure_ascii=False)


def build_prompt(brief: PersonaBrief, spine_text: str) -> tuple[str, str]:
    """The pinned authoring prompt: system and user messages."""
    system = (
        "You draft persona cards for an original, non-canonical professor at "
        "Ashcombe Academy of Magic. The card is reviewed by a human before it "
        "is used. Return one JSON object only, with no code fence and no prose."
    )
    user = f"""\
SHARED PERSONA SPINE (authoritative; do not change its school facts,
boundaries, exam/syllabus/grading refusals or auror copy):

{spine_text}

PERSONA BRIEF (the fixed facts and the voice direction; copy the identity,
stance, facts and templates exactly):

{_brief_json(brief)}

Return JSON with exactly this shape:

{{
  "identity": {{"name": "...", "address": "...", "role": "...", "subject": "..."}},
  "register": {{"stance": "..."}},
  "meta": {{
    "identity": ["...", "...", "..."],
    "scope": ["...", "...", "..."],
    "subject": ["...", "...", "..."],
    "professor": ["...", "...", "..."],
    "boundaries": ["...", "...", "..."],
    "greeting": ["...", "...", "..."]
  }},
  "personal": ["...", "...", "..."],
  "abstain": ["...", "...", "..."],
  "facts": {{"...": "..."}},
  "templates": {{"...": "..."}}
}}

Rules:
- Copy identity, stance, facts and templates from the brief exactly. The facts
  and templates objects must be character-for-character copies: do not render a
  template, fill in its placeholders or invent a key.
- Write 3 to 5 variants for each meta topic, personal and abstain, except
  boundaries, which keeps exactly the three reviewed shapes. Every variant
  must say the same thing in different words; do not add facts.
- Write every meta variant in the professor's own first person ("I"), even
  when the topic is identity or professor; the student is reading the answer
  the professor gives.
- Each meta topic answers its own question and must not borrow another topic's
  job. Every identity variant must contain the brief's address ("Professor
  ...") and say that the professor teaches the subject. Use the address
  naturally ("I am Professor Raman") rather than stacking the full name and
  the address together. scope names the
  subject as theirs and says in every variant that the other four departments
  are taught by colleagues.
  subject says what the subject is: when the brief has a subject_definition
  fact, open with that definition, then the subject_scope; never who teaches
  it, and never uses the words "I teach" (that is identity, not subject).
  professor gives the professor's own history and every detail of the brief's
  background, including the Ministry scheme, the specialism and the founding;
  no background detail may be dropped. boundaries is
  this professor's door, and keeps the reviewed shapes with the subject name
  substituted: (1) "Ask me about <subject>, the set texts, or your own
  preparation. I will answer briefly if you ask about the wider world or about
  me, but I will not invent facts or discuss the examination format." (2) "My
  door is open for <subject>, the set texts and your preparation. Questions
  about the wider world or about me get a brief answer; invented facts and the
  examination format are out of bounds." (3) "Bring me your <subject>
  questions, the set texts and your own preparation. I will answer briefly
  about the wider world or myself, but I will not invent a fact or discuss the
  examination format." Do not restate the shared exam, syllabus or grading
  paragraphs as boundaries.
- Copy the spine's greeting, personal and abstain variants unchanged: they are
  shared policy copy, not persona material.
- Use only the brief's background, voice, teaching and examples. Do not invent
  a fact, date, school history, canon teacher, exam detail or real-world claim.
- Do not add the top-level boundaries, school, tone or pacing: the shared spine
  supplies them. The meta.boundaries variants are required and describe this
  professor's subject guidance. Do not change the shared exam, syllabus,
  grading, school or auror copy.
- Keep the professor original and non-canonical. No URLs, HTML, placeholders,
  model or provider mentions, medical/legal/financial advice.
- Keep each variant between {MIN_VARIANT_CHARS} and {MAX_VARIANT_CHARS} characters.
"""
    return system, user


def parse_generated(text: str) -> GeneratedPersona:
    """Parse the model's JSON draft, ignoring a code fence or trailing prose."""
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    start = value.find("{")
    if start == -1:
        raise PersonaAuthoringError("the model did not return a JSON object")
    try:
        data, _ = json.JSONDecoder().raw_decode(value[start:])
    except json.JSONDecodeError as error:
        raise PersonaAuthoringError(
            f"the model returned invalid JSON: {error}"
        ) from error
    try:
        return GeneratedPersona.model_validate(data)
    except Exception as error:
        raise PersonaAuthoringError(
            f"the model returned an invalid draft: {error}"
        ) from error


async def generate_card(
    brief: PersonaBrief,
    llm: Llm,
    *,
    spine_text: str,
    feedback: list[str] | None = None,
) -> GeneratedPersona:
    """Ask the pinned model for a draft and parse it.

    `feedback` carries the problems from a rejected draft, so a retry can fix
    the exact failures instead of sampling blind.
    """
    system, user = build_prompt(brief, spine_text)
    if feedback:
        user += (
            "\nThe previous draft failed these checks. Return the whole JSON "
            "again and fix every one:\n"
            + "\n".join(f"- {problem}" for problem in feedback)
        )
    text = await llm.generate(system, user)
    return parse_generated(text)


def _variants_problems(where: str, values: list[str]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    if not MIN_VARIANTS <= len(values) <= MAX_VARIANTS:
        problems.append(
            f"{where} must have {MIN_VARIANTS}-{MAX_VARIANTS} variants"
        )
    for value in values:
        text = value.strip()
        if not (MIN_VARIANT_CHARS <= len(text) <= MAX_VARIANT_CHARS):
            problems.append(
                f"{where} variant is outside the length bounds: {text[:60]!r}"
            )
        problems.extend(_content_problems(where, text))
        if _canon_prose(text):
            problems.append(f"{where} names a canon figure")
        if text in seen:
            problems.append(f"{where} repeats a variant: {text[:70]!r}")
        seen.add(text)
    return problems


_PROPER_NOUN = re.compile(r"\b[A-Z][a-z]{2,}\b")
_SUBJECT_TEACHES = re.compile(r"\bI (?:teach|led|lead)\b", re.IGNORECASE)
_OTHER_DEPARTMENTS = re.compile(
    r"\bother (?:four|departments|subjects)\b", re.IGNORECASE
)
_SCOPE_LEAVES = re.compile(r"\b(?:colleagues?|taught|led|belong)\b", re.IGNORECASE)
# A line can start with a capitalised common word; only those are skipped.
_SENTENCE_START = {
    "a", "after", "an", "at", "before", "believes", "during", "fought",
    "he", "her", "his", "holds", "i", "in", "it", "my", "one", "our", "she",
    "served", "studied", "that", "the", "their", "then", "these", "they",
    "this", "those", "was", "we", "were", "works",
}


def _proper_nouns(text: str) -> set[str]:
    """Distinctive names in a background line, minus a common first word."""
    names = {match.lower() for match in _PROPER_NOUN.findall(text)}
    first = text.split()[0] if text.split() else ""
    if first.lower() in _SENTENCE_START:
        names.discard(first.lower())
    return names


def _background_problems(
    brief: PersonaBrief, professor_variants: list[str]
) -> list[str]:
    """Every background line's proper nouns must reach a professor answer.

    The prose may rephrase anything, but a dropped Ministry scheme or Auror
    Office is a lost fact, so the distinctive names are the contract.
    """
    joined = " ".join(professor_variants).lower()
    problems: list[str] = []
    for line in brief.background:
        missing = sorted(
            name for name in _proper_nouns(line) if name not in joined
        )
        if missing:
            problems.append(
                "meta.professor drops background details: "
                + ", ".join(missing)
            )
    return problems


def validate_generated(
    brief: PersonaBrief, generated: GeneratedPersona
) -> list[str]:
    """Content and fixed-field checks before a draft reaches the loader."""
    problems: list[str] = []
    expected_identity = {
        "name": brief.name,
        "address": brief.address,
        "role": brief.role,
        "subject": brief.subject_title,
    }
    if generated.identity != expected_identity:
        problems.append(
            "identity does not match the brief's fixed name, address, role and subject"
        )
    if generated.registration.get("stance") != brief.stance:
        problems.append("register.stance does not match the brief")
    if generated.facts != brief.facts:
        problems.append("facts do not match the brief")
    if generated.templates != brief.templates:
        problems.append("templates do not match the brief")
    for topic in GENERATED_META_TOPICS:
        problems.extend(
            _variants_problems(f"meta.{topic}", generated.meta.get(topic, []))
        )
    problems.extend(_variants_problems("personal", generated.personal))
    problems.extend(_variants_problems("abstain", generated.abstain))
    problems.extend(
        _background_problems(brief, generated.meta.get("professor", []))
    )
    problems.extend(_topic_problems(generated.meta))
    return problems


def _topic_problems(meta: dict[str, list[str]]) -> list[str]:
    """Topic jobs that phrase-level checks can enforce."""
    problems: list[str] = []
    if any(
        _OTHER_DEPARTMENTS.search(variant)
        for variant in meta.get("identity", [])
    ):
        problems.append(
            "meta.identity must not discuss the other departments"
        )
    if any(_SUBJECT_TEACHES.search(variant) for variant in meta.get("subject", [])):
        problems.append(
            "meta.subject describes the subject, not who teaches it"
        )
    if any(
        not (
            _OTHER_DEPARTMENTS.search(variant)
            and _SCOPE_LEAVES.search(variant)
        )
        for variant in meta.get("scope", [])
    ):
        problems.append(
            "meta.scope must say the other four departments are taught by "
            "colleagues"
        )
    return problems


def render_card(generated: GeneratedPersona) -> str:
    """Serialize a draft delta to the TOML the app reads."""

    def value(item: object) -> str:
        if isinstance(item, str):
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, list):
            return (
                "[\n"
                + "".join(f"  {value(entry)},\n" for entry in item)
                + "]"
            )
        raise TypeError(f"cannot serialize {type(item)!r}")

    lines: list[str] = []

    def table(name: str) -> None:
        if lines:
            lines.append("")
        lines.append(f"[{name}]")

    table("identity")
    for key in ("name", "address", "role", "subject"):
        lines.append(f"{key} = {value(generated.identity[key])}")

    table("register")
    lines.append(f"stance = {value(generated.registration['stance'])}")

    table("meta")
    for topic in GENERATED_META_TOPICS:
        lines.append(f"{topic} = {value(generated.meta[topic])}")

    table("personal")
    lines.append(f"response = {value(generated.personal)}")

    table("abstain")
    lines.append(f"response = {value(generated.abstain)}")

    table("facts")
    for key in sorted(generated.facts):
        lines.append(f"{json.dumps(key)} = {value(generated.facts[key])}")

    table("templates")
    for key in sorted(generated.templates):
        lines.append(f"{json.dumps(key)} = {value(generated.templates[key])}")

    return "\n".join(lines).strip() + "\n"


def _spine_data(spine_path: Path = SPINE_PATH) -> dict[str, object]:
    return tomllib.loads(spine_path.read_text(encoding="utf-8"))


def _card_data(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def validate_brief_contract(
    brief: PersonaBrief, spine_path: Path = SPINE_PATH
) -> list[str]:
    """Protect the shared spine facts and templates from a brief.

    A brief may add subject-specific facts and may override the professor's
    own background. It must not move the school, the common education facts or
    the shared templates.
    """
    spine = _spine_data(spine_path)
    spine_facts = {
        str(key): str(value)
        for key, value in (spine.get("facts") or {}).items()
    }
    spine_templates = {
        str(key): str(value)
        for key, value in (spine.get("templates") or {}).items()
    }
    problems: list[str] = []
    for key, value in brief.facts.items():
        if (
            key in spine_facts
            and key not in CARD_OVERRIDABLE_SPINE_FACTS
            and value != spine_facts[key]
        ):
            problems.append(f"brief fact {key!r} changes a shared spine fact")
    for key, value in brief.templates.items():
        if key in spine_templates and value != spine_templates[key]:
            problems.append(
                f"brief template {key!r} changes a shared spine template"
            )
    return problems


def validate_card_delta(
    card_path: Path, spine_path: Path = SPINE_PATH
) -> list[str]:
    """Reject a hand-edited draft that reaches outside the generated sections.

    The generator writes identity, register, meta, personal, abstain, facts and
    templates. The top-level boundaries, school, tone, pacing and the shared
    meta topics belong to the spine and cannot be overridden by a card.
    """
    try:
        card = _card_data(card_path)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"cannot read card {card_path}: {error}"]
    spine = _spine_data(spine_path)
    spine_facts = {
        str(key): str(value)
        for key, value in (spine.get("facts") or {}).items()
    }
    spine_templates = {
        str(key): str(value)
        for key, value in (spine.get("templates") or {}).items()
    }
    problems: list[str] = []
    extra_sections = set(card) - CARD_SECTIONS
    if extra_sections:
        problems.append(
            "card overrides shared spine sections: "
            + ", ".join(sorted(extra_sections))
        )
    identity = card.get("identity", {})
    if not isinstance(identity, dict):
        problems.append("card identity is not a table")
    else:
        extra = set(identity) - CARD_IDENTITY_KEYS
        if extra:
            problems.append(
                "card identity overrides shared fields: "
                + ", ".join(sorted(str(key) for key in extra))
            )
    register = card.get("register", {})
    if not isinstance(register, dict):
        problems.append("card register is not a table")
    elif set(register) - {"stance"}:
        problems.append("card register may only carry stance")
    meta = card.get("meta", {})
    if not isinstance(meta, dict):
        problems.append("card meta is not a table")
    else:
        shared = set(meta) - CARD_META_KEYS
        if shared:
            problems.append(
                "card meta overrides shared topics: "
                + ", ".join(sorted(str(key) for key in shared))
            )
        spine_greeting = (spine.get("meta") or {}).get("greeting")
        if (
            isinstance(spine_greeting, list)
            and isinstance(meta.get("greeting"), list)
            and list(meta["greeting"]) != list(spine_greeting)
        ):
            problems.append(
                "card meta.greeting must match the shared spine"
            )
    for section in ("personal", "abstain"):
        spine_copy = (spine.get(section) or {}).get("response")
        card_copy = card.get(section) or {}
        value = (
            card_copy.get("response")
            if isinstance(card_copy, dict)
            else None
        )
        if (
            isinstance(spine_copy, list)
            and isinstance(value, list)
            and list(value) != list(spine_copy)
        ):
            problems.append(
                f"card {section}.response must match the shared spine"
            )
    facts = card.get("facts", {})
    if not isinstance(facts, dict):
        problems.append("card facts is not a table")
    else:
        for key, value in facts.items():
            key = str(key)
            if (
                key in spine_facts
                and key not in CARD_OVERRIDABLE_SPINE_FACTS
                and str(value) != spine_facts[key]
            ):
                problems.append(f"card fact {key!r} changes a shared spine fact")
    templates = card.get("templates", {})
    if not isinstance(templates, dict):
        problems.append("card templates is not a table")
    else:
        for key, value in templates.items():
            key = str(key)
            if key in spine_templates and str(value) != spine_templates[key]:
                problems.append(
                    f"card template {key!r} changes a shared spine template"
                )
    return problems


def validate_card_fields(
    brief: PersonaBrief, card_path: Path, spine_path: Path = SPINE_PATH
) -> list[str]:
    """Reject facts or templates that are neither in the brief nor the spine."""
    try:
        card = _card_data(card_path)
    except (OSError, tomllib.TOMLDecodeError) as error:
        return [f"cannot read card {card_path}: {error}"]
    spine = _spine_data(spine_path)
    spine_facts = {
        str(key): str(value)
        for key, value in (spine.get("facts") or {}).items()
    }
    spine_templates = {
        str(key): str(value)
        for key, value in (spine.get("templates") or {}).items()
    }
    allowed_facts = set(brief.facts) | set(spine_facts)
    allowed_templates = set(brief.templates) | set(spine_templates)
    problems: list[str] = []
    facts = card.get("facts", {})
    if isinstance(facts, dict):
        for key, value in facts.items():
            key = str(key)
            if key not in allowed_facts:
                problems.append(f"card fact {key!r} is not in the brief or spine")
                continue
            expected = brief.facts.get(key, spine_facts.get(key))
            if expected is not None and str(value) != expected:
                problems.append(f"card fact {key!r} does not match its source")
    templates = card.get("templates", {})
    if isinstance(templates, dict):
        for key, value in templates.items():
            key = str(key)
            if key not in allowed_templates:
                problems.append(
                    f"card template {key!r} is not in the brief or spine"
                )
                continue
            expected = brief.templates.get(key, spine_templates.get(key))
            if expected is not None and str(value) != expected:
                problems.append(
                    f"card template {key!r} does not match its source"
                )
    return problems


def validate_card_file(
    brief: PersonaBrief,
    card_path: Path,
    *,
    spine_path: Path = SPINE_PATH,
) -> list[str]:
    """Load the merged card with the app's loader and compare fixed fields."""
    problems = validate_brief_contract(brief, spine_path)
    problems.extend(validate_card_delta(card_path, spine_path))
    problems.extend(validate_card_fields(brief, card_path, spine_path))
    try:
        persona = load_persona_merged(card_path, spine_path)
    except Exception as error:
        problems.append(f"merged persona card is invalid: {error}")
        return problems
    if persona.name != brief.name:
        problems.append("card name does not match the brief")
    if persona.address != brief.address:
        problems.append("card address does not match the brief")
    if persona.role != brief.role:
        problems.append("card role does not match the brief")
    if persona.subject != brief.subject_title:
        problems.append("card subject does not match the brief")
    if persona.stance != brief.stance:
        problems.append("card stance does not match the brief")
    for key, value in brief.facts.items():
        if persona.facts.get(key) != value:
            problems.append(f"card fact {key!r} does not match the brief")
    for key, value in brief.templates.items():
        if persona.templates.get(key) != value:
            problems.append(f"card template {key!r} does not match the brief")
    if _canon_name(persona.address) or _canon_prose(persona.role):
        problems.append("card identity names a canon figure")
    for where, value in (
        ("address", persona.address),
        ("role", persona.role),
        *[(key, item) for key, item in persona.facts.items()],
        *[(key, item) for key, item in persona.templates.items()],
    ):
        problems.extend(_content_problems(where, value))
    for value in persona.facts.values():
        if _canon_prose(value):
            problems.append("card facts name a canon figure")
    for value in persona.templates.values():
        if _canon_prose(value):
            problems.append("card templates name a canon figure")
    for topic, variants in persona.meta.items():
        problems.extend(
            _variants_problems(f"meta.{topic}", list(variants))
        )
    problems.extend(
        _background_problems(brief, list(persona.meta.get("professor", [])))
    )
    problems.extend(_topic_problems({k: list(v) for k, v in persona.meta.items()}))
    problems.extend(_variants_problems("personal", list(persona.personal)))
    problems.extend(_variants_problems("abstain", list(persona.abstain)))
    return problems


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    # Normalize a Windows checkout's CRLF so provenance does not drift.
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def _path_label(path: Path, root: Path | None) -> str:
    if root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def prompt_sha256(system: str, user: str) -> str:
    return sha256_bytes(f"{system}\n{user}".encode())


def build_provenance(
    *,
    brief: PersonaBrief,
    brief_path: Path,
    card_path: Path,
    provider: str,
    model: str,
    temperature: float,
    prompt_sha: str,
    spine_path: Path = SPINE_PATH,
    root: Path | None = None,
) -> dict[str, object]:
    """The sidecar that makes a generated card reproducible and reviewable."""
    return {
        "schema_version": 1,
        "subject": brief.subject,
        "brief": _path_label(brief_path, root),
        "brief_sha256": sha256_file(brief_path),
        "card": _path_label(card_path, root),
        "card_sha256": sha256_file(card_path),
        "provider": provider,
        "model": model,
        "prompt_version": AUTHORING_PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
        "spine_sha256": sha256_file(spine_path),
        "temperature": temperature,
        "generated_at": datetime.now(UTC).isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
    }


def load_provenance(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PersonaAuthoringError(f"cannot read provenance {path}: {error}") from error
    if not isinstance(data, dict):
        raise PersonaAuthoringError(f"provenance {path} is not an object")
    if data.get("schema_version") != 1:
        raise PersonaAuthoringError(
            f"provenance {path} has an unsupported schema_version"
        )
    return data


def provenance_problems(
    brief: PersonaBrief,
    provenance: dict[str, object],
    brief_path: Path,
    card_path: Path,
    spine_path: Path = SPINE_PATH,
    *,
    require_reviewer: bool,
) -> list[str]:
    """Recompute the recorded prompt, spine and file hashes."""
    spine_text = spine_path.read_text(encoding="utf-8")
    system, user = build_prompt(brief, spine_text)
    problems: list[str] = []
    if provenance.get("schema_version") != 1:
        problems.append("provenance schema_version is not 1")
    if provenance.get("subject") != brief.subject:
        problems.append("provenance subject does not match the brief")
    if provenance.get("brief_sha256") != sha256_file(brief_path):
        problems.append("brief hash drifted")
    if provenance.get("card_sha256") != sha256_file(card_path):
        problems.append("card hash drifted")
    if provenance.get("prompt_version") != AUTHORING_PROMPT_VERSION:
        problems.append("provenance prompt version is stale")
    if provenance.get("prompt_sha256") != prompt_sha256(system, user):
        problems.append("provenance prompt hash does not match the current prompt")
    if provenance.get("spine_sha256") != sha256_file(spine_path):
        problems.append("provenance spine hash drifted")
    if require_reviewer and not str(provenance.get("reviewed_by") or "").strip():
        problems.append("provenance has no reviewer")
    return problems


def publish_card(
    *,
    brief_path: Path,
    draft_path: Path,
    draft_provenance_path: Path,
    card_path: Path,
    provenance_path: Path,
    reviewer: str,
    spine_path: Path = SPINE_PATH,
    root: Path | None = None,
    replace_identity: bool = False,
) -> list[str]:
    """Validate and publish a reviewed draft.

    Returns problems. The live card is written only after the brief, the
    merged card and the draft provenance all pass. A live card with a
    different professor needs `replace_identity`.
    """
    reviewer = reviewer.strip()
    if not reviewer:
        return ["a reviewer name is required"]
    try:
        brief = load_brief(brief_path)
    except PersonaAuthoringError as error:
        return [str(error)]
    repo_root = root or PERSONAS_DIR.parents[1]
    canonical = (
        repo_root
        / "config"
        / "personas"
        / "briefs"
        / f"{brief.subject}.toml"
    ).resolve()
    if brief_path.resolve() != canonical:
        return ["publish requires the canonical brief under config/personas/briefs"]
    if card_path.stem != brief.subject:
        return ["the card filename must match the brief subject"]
    if brief.subject == "dada":
        return ["dada is the standalone seed card; the merged pipeline does not publish it"]
    problems = validate_brief_contract(brief, spine_path)
    problems.extend(validate_card_file(brief, draft_path, spine_path=spine_path))
    if problems:
        return problems
    if not draft_provenance_path.exists():
        return [f"missing draft provenance: {draft_provenance_path}"]
    try:
        provenance = load_provenance(draft_provenance_path)
    except PersonaAuthoringError as error:
        return [str(error)]
    problems = provenance_problems(
        brief,
        provenance,
        brief_path,
        draft_path,
        spine_path,
        require_reviewer=False,
    )
    if problems:
        return problems
    if card_path.exists():
        try:
            current = load_persona_merged(card_path, spine_path)
        except Exception as error:
            return [f"the existing live card is invalid: {error}"]
        if (
            (current.name != brief.name or current.address != brief.address)
            and not replace_identity
        ):
            return [
                "the live card is a different professor; pass replace_identity"
            ]
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(draft_path.read_text(encoding="utf-8"), encoding="utf-8")
    provenance["draft"] = _path_label(draft_path, root)
    provenance["draft_sha256"] = sha256_file(draft_path)
    provenance["card"] = _path_label(card_path, root)
    provenance["card_sha256"] = sha256_file(card_path)
    provenance["reviewed_by"] = reviewer
    provenance["reviewed_at"] = datetime.now(UTC).isoformat()
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return []


def _live_card_subjects(cards_dir: Path) -> set[str]:
    """Live cards the brief pipeline can cover.

    DADA is the standalone seed at ``config/persona.toml`` and is never
    published through this pipeline, so it is not a migration candidate and
    does not block ``--strict``.
    """
    return {
        path.stem
        for path in cards_dir.glob("*.toml")
        if path.stem not in {"spine"}
    }


def check_authoring(
    root: Path,
    *,
    strict: bool = False,
) -> tuple[list[str], list[str]]:
    """Check every brief against its card and provenance.

    Returns (problems, warnings). A live card without a brief is legacy until
    it is migrated; `strict` turns that warning into a problem. Example briefs
    are validated without a card or provenance.
    """
    briefs_dir = root / "config" / "personas" / "briefs"
    cards_dir = root / "config" / "personas"
    provenance_dir = cards_dir / "provenance"
    examples_dir = cards_dir / "examples"
    spine_path = cards_dir / "spine.toml"
    if not spine_path.exists():
        spine_path = SPINE_PATH
    problems: list[str] = []
    warnings: list[str] = []
    live_cards = _live_card_subjects(cards_dir)

    for example_path in (
        sorted(examples_dir.glob("*.toml")) if examples_dir.is_dir() else []
    ):
        try:
            example = load_brief(example_path)
        except PersonaAuthoringError as error:
            problems.append(str(error))
            continue
        problems.extend(validate_brief_contract(example, spine_path))

    brief_paths = sorted(briefs_dir.glob("*.toml")) if briefs_dir.is_dir() else []
    if not brief_paths:
        message = (
            "no persona briefs yet; live cards remain legacy: "
            + ", ".join(sorted(live_cards))
        )
        warnings.append(message)
        if strict:
            problems.append(message)
        for provenance_path in (
            sorted(provenance_dir.glob("*.json"))
            if provenance_dir.is_dir()
            else []
        ):
            problems.append(
                f"provenance without a canonical brief: {provenance_path.name}"
            )
        return problems, warnings

    covered: set[str] = set()
    for brief_path in brief_paths:
        try:
            brief = load_brief(brief_path)
        except PersonaAuthoringError as error:
            problems.append(str(error))
            continue
        if brief_path.stem != brief.subject:
            problems.append(
                f"brief file {brief_path.name} does not match subject {brief.subject}"
            )
        covered.add(brief.subject)
        if brief.subject == "dada":
            problems.append(
                "dada uses the standalone seed card; the merged authoring "
                "pipeline does not publish it"
            )
            continue
        card_path = cards_dir / f"{brief.subject}.toml"
        provenance_path = provenance_dir / f"{brief.subject}.json"
        if not card_path.exists():
            problems.append(f"missing card for {brief.subject}: {card_path}")
            continue
        if not provenance_path.exists():
            problems.append(
                f"missing provenance for {brief.subject}: {provenance_path}"
            )
            continue
        problems.extend(
            validate_card_file(brief, card_path, spine_path=spine_path)
        )
        try:
            provenance = load_provenance(provenance_path)
        except PersonaAuthoringError as error:
            problems.append(str(error))
            continue
        problems.extend(
            provenance_problems(
                brief,
                provenance,
                brief_path,
                card_path,
                spine_path,
                require_reviewer=True,
            )
        )

    for provenance_path in (
        sorted(provenance_dir.glob("*.json"))
        if provenance_dir.is_dir()
        else []
    ):
        if provenance_path.stem not in covered:
            problems.append(
                f"provenance without a canonical brief: {provenance_path.name}"
            )

    uncovered = sorted(live_cards - covered)
    if uncovered:
        message = "live cards without an authoring brief: " + ", ".join(uncovered)
        if strict:
            problems.append(message)
        else:
            warnings.append(message)
    return problems, warnings
