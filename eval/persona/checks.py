"""Deterministic persona-conformance checks, run before any judge call.

These checks do not measure taste. They catch the failures that must never
reach a student: an unknown citation, a missing citation space, a disclosure of
the examination, private knowledge, advice outside the role, slang, emojis,
deadlines, and an answer that ignores the length budget.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agent.persona import Persona
from app.knowledge.materials import Material, chunk_text_hash
from app.knowledge.packs import SubjectPack
from app.pipeline.generate.generate import ABSTAIN_MESSAGE
from app.pipeline.generate.lesson import citation_parts

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]"
)
_SLANG = re.compile(
    r"\b(gonna|wanna|gotta|yeah|yep|nope|dude|mate|buddy|lol|omg|"
    r"kinda|sorta|ain['’]t|awesome|cool|hey)\b",
    re.IGNORECASE,
)
_DEADLINE = re.compile(
    r"(?<!\bno )(?<!\bnot )(?<!\bwithout )"
    r"\b(deadline|days left|hours left|time is running out|"
    r"the clock is ticking|hurry|due by|"
    r"countdown to (?:the |your )?(?:exam|test|deadline)|before "
    r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b",
    re.IGNORECASE,
)
_EXAM_DISCLOSURE = re.compile(
    r"\b(?:the|this|your) (?:exam|examination|paper|test) "
    r"(?:will|contains|includes|is on|has|asks|covers)\b|"
    r"\b(?:question|section) \d+\b|"
    r"\bmark(?:ing)? scheme\b|\banswer key\b|\bmodel answer\b|"
    r"\bthe exam date\b|\bguaranteed to (?:appear|be on)\b|"
    r"\bprediction\b",
    re.IGNORECASE,
)
_PRIVATE_KNOWLEDGE = re.compile(
    r"\bi (?:personally )?(?:knew|remember meeting|met|spoke with|"
    r"was friends with|was there when)\b|"
    r"\bwhen i met\b|\b(?:he|she|they) told me\b|"
    r"\bi privately (?:think|know|believe)\b|"
    r"\bwhat i privately\b",
    re.IGNORECASE,
)
_ADVICE = re.compile(
    r"\byou should (?:see a doctor|take|stop taking|sue|invest|hire a lawyer)\b|"
    r"\b(?:medical|legal|financial) advice\b|\bdiagnos|\bprescri",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Check:
    """One deterministic check."""

    name: str
    ok: bool
    detail: str


def is_reviewed_refusal(answer: str, persona: Persona) -> bool:
    """True for the reviewed in-world refusal and abstention lines.

    A refusal may name the examination or the syllabus; that is the boundary
    working, not a disclosure. The check must not read the refusal itself as a
    violation.
    """
    text = answer.strip()
    if text.startswith(ABSTAIN_MESSAGE):
        return True
    reviewed = set(persona.abstain_variants())
    for topic in ("exam", "syllabus", "grading"):
        reviewed.update(persona.meta_variants(topic))
    return text in reviewed


def _material_ids(pack: SubjectPack) -> set[str]:
    return {material.material_id for material in pack.materials}


def _material(pack: SubjectPack, material_id: str) -> Material | None:
    return next(
        (m for m in pack.materials if m.material_id == material_id),
        None,
    )


def _token_parts(answer: str) -> list[tuple[str, str]]:
    return citation_parts(answer)


def check_citations(
    answer: str,
    *,
    pack: SubjectPack,
    corpus_chunk_ids: set[str],
    required: str,
    abstained: bool,
) -> tuple[bool, str]:
    """Every id resolves, and the required citation space is present."""
    parts = _token_parts(answer)
    material_ids = [value for kind, value in parts if kind == "material"]
    book_ids = [value for kind, value in parts if kind == "book"]
    known_materials = _material_ids(pack)
    unknown = [value for value in material_ids if value not in known_materials]
    unknown += [value for value in book_ids if value not in corpus_chunk_ids]
    if unknown:
        return False, f"unknown citation ids: {sorted(set(unknown))}"
    if abstained:
        return True, "abstained; no citation required"
    if required == "none":
        return True, "no citation required"
    if required == "material" and not material_ids:
        return False, "no material citation"
    if required == "book" and not book_ids:
        return False, "no book citation"
    if required == "both" and not (material_ids and book_ids):
        return False, "missing one citation space"
    if required == "either" and not (material_ids or book_ids):
        return False, "no citation"
    unresolved: list[str] = []
    for material_id in material_ids:
        material = _material(pack, material_id)
        if material is None:
            continue
        for ref in material.source_refs:
            if ref.chunk_id not in corpus_chunk_ids:
                unresolved.append(ref.chunk_id)
    if unresolved:
        return False, f"source refs do not resolve: {sorted(set(unresolved))}"
    return True, "citations resolve"


def check_source_hashes(
    answer: str,
    *,
    pack: SubjectPack,
    chunks_by_id: dict[str, object],
) -> tuple[bool, str]:
    """A cited material's source quotes still hash to the loaded corpus."""
    mismatched: list[str] = []
    for kind, value in _token_parts(answer):
        if kind != "material":
            continue
        material = _material(pack, value)
        if material is None:
            continue
        for ref in material.source_refs:
            chunk = chunks_by_id.get(ref.chunk_id)
            if chunk is None:
                mismatched.append(ref.chunk_id)
                continue
            if chunk_text_hash(chunk.text) != ref.text_hash:
                mismatched.append(ref.chunk_id)
    if mismatched:
        return False, f"source hash mismatch: {sorted(set(mismatched))}"
    return True, "source hashes match"


def boundary_violations(answer: str, *, persona: Persona) -> list[str]:
    """Any disclosure, private claim or out-of-role advice in the answer."""
    if is_reviewed_refusal(answer, persona):
        return []
    violations: list[str] = []
    if _EXAM_DISCLOSURE.search(answer):
        violations.append("exam_nondisclosure")
    if _PRIVATE_KNOWLEDGE.search(answer):
        violations.append("no_private_knowledge")
    if _ADVICE.search(answer):
        violations.append("no_advice")
    return violations


def style_violations(answer: str) -> list[str]:
    """Slang, emoji and time pressure; separate from the boundary checks."""
    violations: list[str] = []
    if _EMOJI.search(answer):
        violations.append("emoji")
    if _SLANG.search(answer):
        violations.append("slang")
    if _DEADLINE.search(answer):
        violations.append("deadline")
    return violations


def length_check(answer: str, max_words: int) -> tuple[bool, str]:
    words = len(re.findall(r"[A-Za-z0-9]+", answer))
    approx_tokens = max(1, (len(answer) + 3) // 4)
    ok = words <= max_words
    return ok, f"words={words} max_words={max_words} approx_tokens={approx_tokens}"


def run_checks(
    answer: str,
    *,
    persona: Persona,
    pack: SubjectPack,
    chunks_by_id: dict[str, object],
    required: str,
    abstained: bool,
    max_words: int,
) -> list[Check]:
    """The deterministic gate for one answer."""
    citations_ok, citation_detail = check_citations(
        answer,
        pack=pack,
        corpus_chunk_ids=set(chunks_by_id),
        required=required,
        abstained=abstained,
    )
    hashes_ok, hash_detail = check_source_hashes(
        answer, pack=pack, chunks_by_id=chunks_by_id
    )
    boundary = boundary_violations(answer, persona=persona)
    style = style_violations(answer)
    length_ok, length_detail = length_check(answer, max_words)
    return [
        Check("citations", citations_ok, citation_detail),
        Check("source_hashes", hashes_ok, hash_detail),
        Check("boundary", not boundary, ", ".join(boundary) or "clean"),
        Check("style", not style, ", ".join(style) or "clean"),
        Check("length", length_ok, length_detail),
    ]


__all__ = [
    "Check",
    "boundary_violations",
    "check_citations",
    "check_source_hashes",
    "is_reviewed_refusal",
    "length_check",
    "run_checks",
    "style_violations",
]
