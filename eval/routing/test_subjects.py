"""Per-subject routing fixture tests, no network or pack required (#222)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.agent.router import contract_decision
from eval.routing.fixtures import (
    SUBJECTS,
    load_routing_items,
    validate_subject_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "subjects.jsonl"
FIXTURE_SHA256 = "bab42217ea8f50cd9fc4004edbc3cb85b7797186df6aa9139de4a8f426168263"

# The fixture is deterministic in CI without the packs: these are the content
# terms the pack vocabulary supplies for each subject's two lesson items.
TEACHING_TERMS = {
    "dada": {"disarm", "boggart"},
    "charms": {"levitat", "banish"},
    "potions": {"polyjuice", "antidote"},
    "transfiguration": {"animagu", "conjur"},
    "herbology": {"mandrake", "greenhouse"},
}


def test_subject_fixture_loads_and_validates():
    items = load_routing_items(FIXTURE)
    validate_subject_fixture(items)
    assert len(items) == 55
    assert {item.subject for item in items} == set(SUBJECTS)


def test_subject_fixture_hash_is_frozen():
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert digest == FIXTURE_SHA256


def test_each_subject_has_the_required_clarify_example():
    items = load_routing_items(FIXTURE)
    for subject in SUBJECTS:
        utterances = {
            item.utterance.lower().rstrip("?.!")
            for item in items
            if item.subject == subject
        }
        assert f"what is included in {subject}" in utterances


def test_subject_fixture_routes_each_contract():
    items = load_routing_items(FIXTURE)
    for item in items:
        decision = contract_decision(
            item.utterance,
            subject=item.subject,
            requested_mode="lesson",
            teaching_terms=TEACHING_TERMS[item.subject],
        )
        assert decision.contract == item.contract, item.item_id
        if item.contract in {"persona", "lore"}:
            assert set(decision.fact_ids) & set(item.fact_ids), item.item_id


def test_subject_fixture_has_no_policy_leak_or_authority_bleed():
    items = load_routing_items(FIXTURE)
    for item in items:
        decision = contract_decision(
            item.utterance,
            subject=item.subject,
            requested_mode="lesson",
            teaching_terms=TEACHING_TERMS[item.subject],
        )
        if item.contract == "policy":
            assert decision.contract == "policy", item.item_id
        if item.contract in {"persona", "lore"}:
            assert decision.contract not in {"lesson", "answer"}, item.item_id
        if item.contract == "lesson":
            assert decision.contract not in {"persona", "lore", "fact"}, item.item_id
        if item.contract == "abstain":
            assert decision.contract == "abstain", item.item_id
