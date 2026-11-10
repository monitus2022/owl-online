"""Typed citation authority and the cross-type checker (#218).

The routing contract gives each answer a single knowledge authority:

- ``policy:script:<id>`` for a reviewed refusal;
- ``persona:<fact_id>`` for a card fact;
- ``lore:<fact_id>`` for a setting-pack fact;
- ``lesson:<doc_id>#<span>`` for a teaching span.

The checker is deterministic and runs on the final payload. It is an authority
check, not a prompt instruction: a setting answer with a lesson cite is invalid
even when the book mentions the same noun.
"""

from __future__ import annotations

from dataclasses import dataclass

POLICY = "policy"
PERSONA = "persona"
LORE = "lore"
LESSON = "lesson"
AUTHORITIES = frozenset({POLICY, PERSONA, LORE, LESSON})

_POLICY_PREFIX = "policy:script:"
_PERSONA_PREFIX = "persona:"
_LORE_PREFIX = "lore:"
_LESSON_PREFIX = "lesson:"

SETTING_MODES = frozenset({"fact", "persona", "lore"})
TEACHING_MODES = frozenset({"lesson", "practice", "feedback"})
SILENT_MODES = frozenset({"meta", "personal", "clarify", "abstain"})


@dataclass(frozen=True)
class TypedCitation:
    authority: str
    value: str
    raw: str


def parse_citation(raw: str) -> TypedCitation | None:
    """Parse one typed citation, or return None when the form is unknown."""
    if raw.startswith(_POLICY_PREFIX):
        value = raw[len(_POLICY_PREFIX):]
        if value:
            return TypedCitation(POLICY, value, raw)
        return None
    if raw.startswith(_PERSONA_PREFIX):
        value = raw[len(_PERSONA_PREFIX):]
        if value:
            return TypedCitation(PERSONA, value, raw)
        return None
    if raw.startswith(_LORE_PREFIX):
        value = raw[len(_LORE_PREFIX):]
        if value:
            return TypedCitation(LORE, value, raw)
        return None
    if raw.startswith(_LESSON_PREFIX):
        value = raw[len(_LESSON_PREFIX):]
        if "#" not in value:
            return None
        doc_id, span = value.split("#", 1)
        if doc_id and span:
            return TypedCitation(LESSON, doc_id, raw)
    return None


def typed_from_legacy(
    citations: list[str],
    lore_citations: list[str],
    material_citations: list[str],
) -> list[str]:
    """Map the pre-#218 fields to typed citations for older/cached results."""
    typed: list[str] = []
    for chunk_id in citations:
        typed.append(f"lesson:{chunk_id}#{chunk_id}")
    for lore_id in lore_citations:
        typed.append(f"lore:{lore_id}")
    for material_id in material_citations:
        typed.append(f"lesson:{material_id}#{material_id}")
    return list(dict.fromkeys(typed))


def check_authority(
    citations: list[str],
    *,
    mode: str,
    abstained: bool = False,
    needs_input: bool = False,
) -> list[str]:
    """Return the authority errors for one final answer.

    An empty list is valid. A setting answer must carry a persona or lore cite;
    a teaching answer must carry a lesson cite; policy must carry a script cite;
    scripted meta, personal, clarify and abstain answers carry no citations.
    """
    if needs_input and not citations:
        # A feedback request with no student answer has nothing to cite.
        return []
    errors: list[str] = []
    parsed: list[TypedCitation] = []
    for raw in citations:
        citation = parse_citation(raw)
        if citation is None:
            errors.append(f"unknown citation form: {raw}")
        else:
            parsed.append(citation)
    authorities = {citation.authority for citation in parsed}

    if mode == "policy":
        if not abstained and POLICY not in authorities:
            errors.append("policy answer has no policy:script citation")
        extra = authorities - {POLICY}
        if extra:
            errors.append(f"policy answer carries {sorted(extra)} citations")
    elif mode in SETTING_MODES:
        if not abstained and not (authorities & {PERSONA, LORE}):
            errors.append("setting answer has no persona or lore citation")
        extra = authorities & {LESSON, POLICY}
        if extra:
            errors.append(f"setting answer carries {sorted(extra)} citations")
    elif mode == "answer":
        # The corpus path can answer a setting question from lore or a book
        # question from a lesson span; a mixed authority is the error.
        if POLICY in authorities:
            errors.append("answer carries policy citations")
        if authorities & {PERSONA, LORE} and LESSON in authorities:
            errors.append("answer mixes setting and lesson citations")
        if not abstained and not (authorities & {LESSON, PERSONA, LORE}):
            errors.append("answer has no lesson, persona or lore citation")
    elif mode in TEACHING_MODES:
        if not abstained and LESSON not in authorities:
            errors.append("teaching answer has no lesson citation")
        extra = authorities & {PERSONA, LORE, POLICY}
        if extra:
            errors.append(f"teaching answer carries {sorted(extra)} citations")
    elif mode in SILENT_MODES:
        if parsed:
            errors.append(f"{mode} answer should carry no citations")
    else:
        errors.append(f"unknown mode: {mode}")
    return errors


__all__ = [
    "AUTHORITIES",
    "LESSON",
    "LORE",
    "PERSONA",
    "POLICY",
    "SETTING_MODES",
    "SILENT_MODES",
    "TEACHING_MODES",
    "TypedCitation",
    "check_authority",
    "parse_citation",
    "typed_from_legacy",
]
