"""The multi-subject persona registry (#222), no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.persona import (
    META_TOPICS,
    PERSONA,
    PERSONAS,
    REQUIRED_BOUNDARIES,
    for_subject,
)

EXPECTED = {
    "dada": ("Alistair Crane", "Professor Crane", "Defense Against the Dark Arts"),
    "potions": ("Edith Vale", "Professor Vale", "Potions"),
    "transfiguration": ("Marcus Hale", "Professor Hale", "Transfiguration"),
    "charms": ("Priya Raman", "Professor Raman", "Charms"),
    "herbology": ("Nell Ashby", "Professor Ashby", "Herbology"),
}
SHARED_TOPICS = ("exam", "syllabus", "grading", "school", "auror")
FORMAT_WORDS = (
    "paper",
    "practical",
    "outstanding",
    "troll",
    "written",
    "demonstration",
    "mark scheme",
)
TIME_WORDS = ("deadline", "tomorrow", "next week", "hurry", "countdown", "tonight")


def test_registry_has_the_five_subject_cards():
    assert set(PERSONAS) == set(EXPECTED)
    assert PERSONAS["dada"] is PERSONA


def test_each_card_has_every_meta_topic_and_boundary():
    for subject, persona in PERSONAS.items():
        for topic in META_TOPICS:
            variants = persona.meta_variants(topic)
            assert variants, (subject, topic)
            assert all(text.strip() for text in variants), (subject, topic)
        assert set(persona.boundaries) == set(REQUIRED_BOUNDARIES), subject
        assert persona.personal_variants(), subject
        assert persona.abstain_variants(), subject


def test_each_card_names_its_own_subject_and_professor():
    for subject, (name, address, subject_name) in EXPECTED.items():
        persona = for_subject(subject)
        assert persona.name == name, subject
        assert persona.address == address, subject
        assert persona.subject == subject_name, subject
        assert any(
            address in text for text in persona.meta_variants("identity")
        ), subject
        assert any(
            subject_name in text for text in persona.meta_variants("scope")
        ), subject


def test_cards_share_the_policy_spine():
    for subject in EXPECTED:
        if subject == "dada":
            continue
        persona = for_subject(subject)
        assert persona.school == PERSONA.school, subject
        assert persona.tone == PERSONA.tone, subject
        assert persona.pacing == PERSONA.pacing, subject
        assert persona.boundaries == PERSONA.boundaries, subject
        assert persona.abstain_variants() == PERSONA.abstain_variants(), subject
        for topic in SHARED_TOPICS:
            assert (
                persona.meta_variants(topic) == PERSONA.meta_variants(topic)
            ), (subject, topic)


def test_policy_topics_do_not_disclose_the_exam_format():
    for subject, persona in PERSONAS.items():
        for topic in ("exam", "syllabus", "grading"):
            for text in persona.meta_variants(topic):
                folded = text.casefold()
                for word in FORMAT_WORDS:
                    assert word not in folded, (subject, topic, word, text)


def test_cards_do_not_impose_time_pressure():
    for subject, persona in PERSONAS.items():
        texts = list(persona.personal_variants()) + list(
            persona.abstain_variants()
        )
        for topic in META_TOPICS:
            texts.extend(persona.meta_variants(topic))
        for text in texts:
            folded = text.casefold()
            for word in TIME_WORDS:
                assert word not in folded, (subject, word, text)


def test_for_subject_rejects_an_unknown_subject():
    with pytest.raises(KeyError, match="no persona card"):
        for_subject("astronomy")


def test_dada_seed_is_the_raw_toml_card():
    import tomllib

    from app.agent.persona import (
        PERSONA_PATH,
        SPINE_PATH,
        _deep_merge,
        _persona_from_data,
    )

    raw = tomllib.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    assert _persona_from_data(raw) == PERSONA
    spine = tomllib.loads(SPINE_PATH.read_text(encoding="utf-8"))
    assert _deep_merge(spine, raw) == raw


def test_the_four_cards_share_the_spine_greeting():
    greetings = {
        for_subject(subject).meta_variants("greeting")
        for subject in EXPECTED
        if subject != "dada"
    }
    assert len(greetings) == 1
    assert PERSONA.meta_variants("greeting") not in greetings


def test_personas_doc_lists_every_card_variant():
    doc = (Path(__file__).resolve().parents[1] / "docs" / "personas.md").read_text(
        encoding="utf-8"
    )
    for subject in EXPECTED:
        if subject == "dada":
            continue
        persona = for_subject(subject)
        for topic in (
            "identity",
            "scope",
            "subject",
            "professor",
            "boundaries",
            "greeting",
        ):
            for text in persona.meta_variants(topic):
                assert text in doc, (subject, topic, text)
        for text in persona.personal_variants():
            assert text in doc, (subject, "personal", text)
