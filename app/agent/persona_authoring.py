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

from app.agent.persona import SPINE_PATH, load_persona_merged
from app.knowledge.taxonomy import SUBJECT_KEYS, known_subject
from app.providers.contracts import Llm

AUTHORING_PROMPT_VERSION = "authoring-v1"

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

# Canon school staff must not become the professor. The school and the
# founders are original; a generated name cannot be a canon teacher.
CANON_STAFF = frozenset(
    name.lower()
    for name in (
        "Dumbledore",
        "McGonagall",
        "Snape",
        "Flitwick",
        "Sprout",
        "Hagrid",
        "Moody",
        "Lupin",
        "Umbridge",
        "Slughorn",
        "Lockhart",
        "Quirrell",
        "Trelawney",
        "Binns",
        "Burbage",
        "Vector",
        "Sinistra",
        "Hooch",
        "Pomfrey",
        "Filch",
        "Pince",
        "Kettleburn",
        "Grubbly-Plank",
    )
)

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
        lowered = self.name.lower()
        if any(staff in lowered for staff in CANON_STAFF):
            raise ValueError(
                "the professor's name must be original, not a canon staff name"
            )
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
- Copy identity, stance, facts and templates from the brief exactly.
- Write 3 to 5 variants for each meta topic, personal and abstain. Every
  variant must say the same thing in different words; do not add facts.
- Use only the brief's background, voice, teaching and examples. Do not invent
  a fact, date, school history, canon teacher, exam detail or real-world claim.
- Do not add boundaries, school, tone or pacing: the shared spine supplies
  them. Do not change the shared exam, syllabus, grading, school or auror copy.
- Keep the professor original and non-canonical. No URLs, HTML, placeholders,
  model or provider mentions, medical/legal/financial advice.
- Keep each variant between {MIN_VARIANT_CHARS} and {MAX_VARIANT_CHARS} characters.
"""
    return system, user


def _strip_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    start = value.find("{")
    end = value.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise PersonaAuthoringError("the model did not return a JSON object")
    return value[start : end + 1]


def parse_generated(text: str) -> GeneratedPersona:
    """Parse the model's JSON draft."""
    try:
        data = json.loads(_strip_fence(text))
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
) -> GeneratedPersona:
    """Ask the pinned model for a draft and parse it."""
    system, user = build_prompt(brief, spine_text)
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
        if any(staff in lowered for staff in CANON_STAFF):
            problems.append(f"{where} names a canon staff member")
        if text in seen:
            problems.append(f"{where} repeats a variant")
        seen.add(text)
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


def validate_card_file(
    brief: PersonaBrief,
    card_path: Path,
    *,
    spine_path: Path = SPINE_PATH,
) -> list[str]:
    """Load the merged card with the app's loader and compare fixed fields."""
    try:
        persona = load_persona_merged(card_path, spine_path)
    except Exception as error:
        return [f"merged persona card is invalid: {error}"]
    problems: list[str] = []
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
    for topic, variants in persona.meta.items():
        problems.extend(
            _variants_problems(f"meta.{topic}", list(variants))
        )
    problems.extend(_variants_problems("personal", list(persona.personal)))
    problems.extend(_variants_problems("abstain", list(persona.abstain)))
    return problems


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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
) -> dict[str, object]:
    """The sidecar that makes a generated card reproducible and reviewable."""
    return {
        "schema_version": 1,
        "subject": brief.subject,
        "brief": str(brief_path),
        "brief_sha256": sha256_file(brief_path),
        "card": str(card_path),
        "card_sha256": sha256_file(card_path),
        "provider": provider,
        "model": model,
        "prompt_version": AUTHORING_PROMPT_VERSION,
        "prompt_sha256": prompt_sha,
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
    return data


def check_authoring(
    root: Path,
    *,
    strict: bool = False,
) -> tuple[list[str], list[str]]:
    """Check every brief against its card and provenance.

    Returns (problems, xwarnings). A live card without a brief is legacy until
    it is migrated; `strict` turns that warning into a problem.
    """
    briefs_dir = root / "config" / "personas" / "briefs"
    cards_dir = root / "config" / "personas"
    provenance_dir = cards_dir / "provenance"
    problems: list[str] = []
    warnings: list[str] = []

    brief_paths = sorted(briefs_dir.glob("*.toml")) if briefs_dir.is_dir() else []
    if not brief_paths:
        message = "no persona briefs yet; the five live cards remain legacy"
        warnings.append(message)
        if strict:
            problems.append(message)
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
        problems.extend(validate_card_file(brief, card_path))
        try:
            provenance = load_provenance(provenance_path)
        except PersonaAuthoringError as error:
            problems.append(str(error))
            continue
        if provenance.get("subject") != brief.subject:
            problems.append(f"provenance subject does not match {brief.subject}")
        if provenance.get("brief_sha256") != sha256_file(brief_path):
            problems.append(f"brief hash drifted for {brief.subject}")
        if provenance.get("card_sha256") != sha256_file(card_path):
            problems.append(f"card hash drifted for {brief.subject}")
        if not provenance.get("reviewed_by"):
            problems.append(f"card {brief.subject} has no reviewer")

    live_cards = {
        path.stem
        for path in cards_dir.glob("*.toml")
        if path.stem not in {"spine"}
    }
    live_cards.add("dada")
    uncovered = sorted(live_cards - covered)
    if uncovered:
        message = "live cards without an authoring brief: " + ", ".join(uncovered)
        if strict:
            problems.append(message)
        else:
            warnings.append(message)
    return problems, warnings
