"""Persona-conformance fixtures: route, scope, citation and voice anchors.

This set is separate from `eval/gold/questions.jsonl`. The gold set measures
factual answer quality on the corpus path; this set measures whether the lesson
and persona surfaces stay in voice, cite the right space and refuse what they
must. Scenario questions are original; no corpus or pack prose is stored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.agent.persona import META_TOPICS as PERSONA_META_TOPICS

ROUTES = frozenset(
    {"lesson", "meta", "personal", "answer", "policy", "fact", "clarify", "abstain"}
)
SCOPES = frozenset({"in_pack", "mixed", "off_pack", "abstained"})
CITATIONS = frozenset({"material", "book", "both", "either", "none"})
BOUNDARIES = frozenset(
    {"exam_nondisclosure", "no_private_knowledge", "no_advice", "no_injection"}
)
META_TOPICS = frozenset(PERSONA_META_TOPICS)


@dataclass(frozen=True)
class PersonaScenario:
    """One scenario and the checks it must pass."""

    scenario_id: str
    question: str
    route: str
    category: str
    citation: str
    scopes: tuple[str, ...] = ()
    topic: str | None = None
    boundary: str | None = None
    anchors: tuple[str, ...] = ()
    max_words: int = 220
    note: str = ""

    def scope_ok(self, scope: str | None) -> bool:
        return not self.scopes or scope in self.scopes

    def boundary_ok(self, boundary: str | None) -> bool:
        return self.boundary is None or self.boundary == boundary


def _require_str(record: dict[str, object], key: str, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: missing or empty {key!r}")
    return value.strip()


def _optional_str(record: dict[str, object], key: str, where: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: {key!r} must be a non-empty string or null")
    return value.strip()


def _string_tuple(record: dict[str, object], key: str, where: str) -> tuple[str, ...]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{where}: {key!r} must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def parse_scenario(record: dict[str, object], where: str) -> PersonaScenario:
    scenario_id = _require_str(record, "id", where)
    question = _require_str(record, "question", where)
    route = _require_str(record, "route", where)
    category = _require_str(record, "category", where)
    citation = _require_str(record, "citation", where)
    if route not in ROUTES:
        raise ValueError(f"{where}: unknown route {route!r}")
    if citation not in CITATIONS:
        raise ValueError(f"{where}: unknown citation mode {citation!r}")
    scopes = _string_tuple(record, "scope", where)
    unknown_scopes = set(scopes) - SCOPES
    if unknown_scopes:
        raise ValueError(f"{where}: unknown scope(s) {sorted(unknown_scopes)}")
    topic = _optional_str(record, "topic", where)
    if topic is not None and topic not in META_TOPICS:
        raise ValueError(f"{where}: unknown meta topic {topic!r}")
    if route == "meta" and topic is None:
        raise ValueError(f"{where}: a meta scenario needs a topic")
    if route == "meta" and citation != "none":
        raise ValueError(f"{where}: a meta scenario has no citations")
    if route == "personal" and citation != "none":
        raise ValueError(f"{where}: a personal scenario has no citations")
    boundary = _optional_str(record, "boundary", where)
    if boundary is not None and boundary not in BOUNDARIES:
        raise ValueError(f"{where}: unknown boundary {boundary!r}")
    anchors = _string_tuple(record, "anchors", where)
    max_words = record.get("max_words", 220)
    if not isinstance(max_words, int) or max_words < 1:
        raise ValueError(f"{where}: max_words must be a positive integer")
    note = _optional_str(record, "note", where) or ""
    return PersonaScenario(
        scenario_id=scenario_id,
        question=question,
        route=route,
        category=category,
        citation=citation,
        scopes=scopes,
        topic=topic,
        boundary=boundary,
        anchors=anchors,
        max_words=max_words,
        note=note,
    )


def load_persona_scenarios(path: Path) -> list[PersonaScenario]:
    """Load and validate the fixture; duplicate ids fail loudly."""
    scenarios: list[PersonaScenario] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: each line must be an object")
        scenario = parse_scenario(record, f"{path}:{line_number}")
        if scenario.scenario_id in seen:
            raise ValueError(f"{path}:{line_number}: duplicate id {scenario.scenario_id!r}")
        seen.add(scenario.scenario_id)
        scenarios.append(scenario)
    if not scenarios:
        raise ValueError(f"{path}: no scenarios")
    return scenarios


__all__ = [
    "PersonaScenario",
    "load_persona_scenarios",
    "parse_scenario",
]
