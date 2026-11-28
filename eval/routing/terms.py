"""Teaching-term helper shared by the two #327 measurement scripts.

The deterministic baseline and the classifier comparison must use the same
terms, or a turn can be `lesson` in one column and `abstain` in the other and
the classifier's gain is overstated. The published DADA pack is the source.
"""

from __future__ import annotations

from pathlib import Path

from app.knowledge.packs import load_subject_pack
from app.knowledge.taxonomy import SUBJECT_NAMES
from app.knowledge.terms import content_terms

REPO = Path(__file__).resolve().parents[2]


def teaching_terms(subject: str) -> set[str] | None:
    """The pack vocabulary for a subject, or None when the pack is absent."""
    path = REPO / "data" / "subjects" / subject
    if not path.exists():
        return None
    pack = load_subject_pack(path)
    terms: set[str] = set()
    terms.update(content_terms(subject))
    terms.update(content_terms(SUBJECT_NAMES.get(subject, subject)))
    for concept in pack.concepts:
        terms.update(content_terms(concept.title))
        for alias in concept.aliases:
            terms.update(content_terms(alias))
    for material in pack.materials:
        terms.update(content_terms(material.text))
    return terms


__all__ = ["REPO", "teaching_terms"]
