"""Persona fixture shape and validation, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.persona.fixtures import load_persona_scenarios, parse_scenario

FIXTURE = Path(__file__).parent / "fixtures" / "conformance.jsonl"


def test_fixture_covers_the_required_categories():
    scenarios = load_persona_scenarios(FIXTURE)
    assert 20 <= len(scenarios) <= 30
    categories = {scenario.category for scenario in scenarios}
    assert {
        "in_pack",
        "in_pack_gap",
        "mixed",
        "off_pack",
        "meta",
        "personal",
        "off_topic",
        "adversarial",
    } <= categories
    assert any(scenario.max_words > 220 for scenario in scenarios)
    assert any(scenario.boundary == "no_private_knowledge" for scenario in scenarios)
    assert any(scenario.boundary == "no_advice" for scenario in scenarios)


def test_every_meta_scenario_has_a_topic():
    for scenario in load_persona_scenarios(FIXTURE):
        if scenario.route == "meta":
            assert scenario.topic is not None


def test_duplicate_id_fails(tmp_path):
    path = tmp_path / "fixture.jsonl"
    row = (
        '{"id":"x","category":"meta","question":"Who are you?","route":"meta",'
        '"topic":"identity","citation":"none"}'
    )
    path.write_text(row + "\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate id"):
        load_persona_scenarios(path)


def test_meta_without_topic_fails():
    with pytest.raises(ValueError, match="needs a topic"):
        parse_scenario(
            {
                "id": "x",
                "category": "meta",
                "question": "Who are you?",
                "route": "meta",
                "citation": "none",
            },
            "test",
        )
