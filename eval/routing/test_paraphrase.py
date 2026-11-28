"""Frozen #327 phrase-coverage slices and the deterministic hard cases."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.agent.router import contract_decision
from eval.routing.fixtures import (
    load_multiturn_items,
    load_routing_items,
    validate_multiturn_fixture,
    validate_must_not_fixture,
    validate_paraphrase_fixture,
)

FIXTURES = Path(__file__).parent / "fixtures"
HASHES = {
    "paraphrase.jsonl": "6fa1e56104de4ce2b715e4b06f75278cb5edbc25d8ab816232a26fa847689c34",
    "must_not.jsonl": "4d5ecb3b7bfe8f27c4a64572222ef31a1e1bf2ffa843917ca83b2836d47a49bd",
    "multiturn.jsonl": "938089f841c5ca4547b488c11c5147d05627c532c96a74a0b5a35a315067400a",
}
TERMS = {"boggart", "dementor", "expelliarmus", "patronus", "curse"}


def test_fixture_hashes_are_frozen():
    for name, digest in HASHES.items():
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest


def test_slices_load_and_validate():
    paraphrase = load_routing_items(FIXTURES / "paraphrase.jsonl")
    validate_paraphrase_fixture(paraphrase)
    must_not = load_routing_items(FIXTURES / "must_not.jsonl")
    validate_must_not_fixture(must_not)
    multiturn = load_multiturn_items(FIXTURES / "multiturn.jsonl")
    validate_multiturn_fixture(multiturn)
    assert len(paraphrase) == 77
    assert len(must_not) == 40
    assert len(multiturn) == 22


@pytest.mark.parametrize(
    "question",
    [
        "What is this academy?",
        "Tell me about this academy.",
        "What kind of school is this?",
        "When was it founded?",
        "What departments are there?",
        "Who are the founders?",
        "Who runs this place?",
        "Where am I?",
    ],
)
def test_school_phrases_route_to_school_001(question):
    decision = contract_decision(
        question, subject="dada", requested_mode="lesson", teaching_terms=TERMS
    )
    assert decision.contract == "lore", question
    assert decision.fact_ids == ("lore:school-001",), question


@pytest.mark.parametrize(
    "question",
    [
        "When was this place founded, and what is the exam format?",
        "Who founded the school and what will be on the exam?",
        "How many students are there, and how are exams graded?",
    ],
)
def test_setting_and_assessment_in_one_turn_clarifies(question):
    decision = contract_decision(
        question, subject="dada", requested_mode="lesson", teaching_terms=TERMS
    )
    assert decision.contract == "clarify", question


def test_must_not_slice_has_no_lore_route():
    for item in load_routing_items(FIXTURES / "must_not.jsonl"):
        decision = contract_decision(
            item.utterance,
            subject=item.subject,
            requested_mode="lesson",
            teaching_terms=TERMS,
        )
        assert decision.contract != "lore", item.item_id


def test_multiturn_fixture_contracts_are_in_the_router_vocabulary():
    contracts = {item.final_contract for item in load_multiturn_items(FIXTURES / "multiturn.jsonl")}
    assert {"lore", "clarify", "policy", "persona", "lesson"} <= contracts
