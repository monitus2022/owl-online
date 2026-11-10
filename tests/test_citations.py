"""Typed citation authority and the cross-type checker (#218)."""

from __future__ import annotations

import pytest

from app.knowledge.citations import (
    check_authority,
    parse_citation,
    typed_from_legacy,
)


@pytest.mark.parametrize(
    ("raw", "authority", "value"),
    [
        ("policy:script:assessment.dada", "policy", "assessment.dada"),
        ("persona:professor.education", "persona", "professor.education"),
        ("lore:school-001", "lore", "school-001"),
        (
            "lesson:dada-dueling-disarming-charm#b1-c01-0000",
            "lesson",
            "dada-dueling-disarming-charm",
        ),
    ],
)
def test_parse_citation_accepts_the_four_forms(raw, authority, value):
    parsed = parse_citation(raw)
    assert parsed is not None
    assert parsed.authority == authority
    assert parsed.value == value
    assert parsed.raw == raw


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "b1-c01-0000",
        "policy:",
        "policy:script:",
        "persona:",
        "lore:",
        "lesson:",
        "lesson:no-span",
        "lesson:#span",
        "lesson:doc#",
        "unknown:thing",
    ],
)
def test_parse_citation_rejects_unknown_forms(raw):
    assert parse_citation(raw) is None


def test_policy_answer_requires_a_script_and_rejects_other_authorities():
    assert check_authority(
        ["policy:script:assessment.dada"], mode="policy"
    ) == []
    assert check_authority([], mode="policy")
    assert check_authority(["lore:school-001"], mode="policy")
    assert check_authority(
        ["policy:script:assessment.dada", "lore:school-001"], mode="policy"
    )


def test_setting_answer_requires_persona_or_lore_and_rejects_lesson():
    assert check_authority(["lore:school-001"], mode="fact") == []
    assert check_authority(["persona:identity"], mode="fact") == []
    assert check_authority([], mode="fact")
    assert check_authority(["lesson:doc#span"], mode="fact")
    assert check_authority(["policy:script:assessment.dada"], mode="fact")


def test_teaching_answer_requires_lesson_and_rejects_lore():
    assert check_authority(["lesson:doc#span"], mode="lesson") == []
    assert check_authority([], mode="lesson")
    assert check_authority(["lore:school-001"], mode="lesson")
    assert check_authority(["persona:identity"], mode="lesson")
    assert check_authority(["policy:script:assessment.dada"], mode="lesson")


def test_answer_path_allows_a_setting_or_a_lesson_citation_but_not_both():
    assert check_authority(["lore:school-001"], mode="answer") == []
    assert check_authority(["persona:identity"], mode="answer") == []
    assert check_authority(["lesson:doc#span"], mode="answer") == []
    assert check_authority([], mode="answer")
    assert check_authority(["policy:script:assessment.dada"], mode="answer")
    assert check_authority(
        ["lesson:doc#span", "lore:school-001"], mode="answer"
    )


def test_abstained_answers_do_not_need_a_citation():
    assert check_authority([], mode="lesson", abstained=True) == []
    assert check_authority([], mode="fact", abstained=True) == []
    assert check_authority([], mode="policy", abstained=True) == []


def test_scripted_modes_carry_no_citations():
    for mode in ("meta", "personal", "clarify", "abstain"):
        assert check_authority([], mode=mode) == []
        assert check_authority(["lore:school-001"], mode=mode)


def test_unknown_citation_and_mode_are_errors():
    assert check_authority(["b1-c01-0000"], mode="answer")
    assert check_authority([], mode="chat")


def test_typed_from_legacy_maps_the_old_fields():
    assert typed_from_legacy(
        ["b1-c01-0000"],
        ["school-001"],
        ["dada-test-material"],
    ) == [
        "lesson:b1-c01-0000#b1-c01-0000",
        "lore:school-001",
        "lesson:dada-test-material#dada-test-material",
    ]
