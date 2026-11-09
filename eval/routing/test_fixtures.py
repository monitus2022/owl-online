"""Contract/authority routing fixture tests, no network."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from eval.routing.fixtures import (
    load_routing_items,
    parse_item,
    validate_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "contracts.jsonl"
FIXTURE_SHA256 = "f703a812c188b605728a34cf3f851ec86cf73b5c937429c91e96d4093120a6f2"


def test_fixture_loads_and_validates():
    items = load_routing_items(FIXTURE)
    validate_fixture(items)
    assert len(items) >= 200
    assert {item.contract for item in items} == {
        "policy",
        "persona",
        "lore",
        "lesson",
        "abstain",
        "clarify",
    }


def test_required_examples_are_labelled():
    items = {item.utterance.lower().rstrip("?.!"): item for item in load_routing_items(FIXTURE)}
    education = items["where did you study when you are young"]
    assert education.contract == "persona"
    assert education.fact_ids == ("persona:professor.education",)
    scope = items["what is included in dada"]
    assert scope.contract == "clarify"
    assert "lore:dada-001" in scope.fact_ids
    assert "policy:assessment.dada" in scope.fact_ids


def test_holdout_family_is_present_and_separate():
    items = load_routing_items(FIXTURE)
    holdout = [item for item in items if item.holdout]
    assert len(holdout) >= 8
    assert any("persona:professor.education" in item.fact_ids for item in holdout)
    assert any(item.contract == "clarify" for item in holdout)


def test_fixture_hash_is_frozen():
    if not FIXTURE_SHA256:
        pytest.skip("fixture hash is not pinned yet")
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert digest == FIXTURE_SHA256


def test_duplicate_id_fails(tmp_path):
    path = tmp_path / "fixture.jsonl"
    row = (
        '{"id":"x","utterance":"Who are you?","contract":"persona",'
        '"fact_ids":["persona:identity"],"fact_present":true,'
        '"category":"identity"}'
    )
    path.write_text(row + "\n" + row + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate id"):
        load_routing_items(path)


def test_unknown_contract_fails():
    with pytest.raises(ValueError, match="unknown contract"):
        parse_item(
            {
                "id": "x",
                "utterance": "Who are you?",
                "contract": "chat",
                "fact_ids": [],
                "fact_present": False,
                "category": "identity",
            },
            "test",
        )


def test_fact_prefix_must_match_contract():
    with pytest.raises(ValueError, match="fact ids do not match"):
        parse_item(
            {
                "id": "x",
                "utterance": "Who are you?",
                "contract": "persona",
                "fact_ids": ["lore:school-001"],
                "fact_present": True,
                "category": "identity",
            },
            "test",
        )


def test_fact_present_must_match_fact_ids():
    with pytest.raises(ValueError, match="fact_present"):
        parse_item(
            {
                "id": "x",
                "utterance": "Who are you?",
                "contract": "persona",
                "fact_ids": [],
                "fact_present": True,
                "category": "identity",
            },
            "test",
        )
