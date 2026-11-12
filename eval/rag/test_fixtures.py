"""Fixture shape tests; no network, no model calls."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from eval.rag.fixtures import load_conversations, load_lesson_items

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_lesson_fixture_has_the_expected_slices():
    items = load_lesson_items(FIXTURES / "lesson.jsonl")
    assert len(items) == 62
    assert {item.subject for item in items} == {
        "dada",
        "charms",
        "potions",
        "transfiguration",
        "herbology",
    }
    assert Counter(item.slice_name for item in items) == {
        "in_pack": 20,
        "paraphrase": 10,
        "multi_concept": 20,
        "mixed": 1,
        "off_pack": 1,
        "abstain": 10,
    }
    assert sum(item.answerable for item in items) == 52
    assert sum(not item.answerable for item in items) == 10


def test_every_answerable_lesson_item_has_materials_and_refs():
    items = load_lesson_items(FIXTURES / "lesson.jsonl")
    for item in items:
        if not item.answerable:
            assert item.expected_material_ids == ()
            assert item.expected_source_refs == ()
            assert item.expected_chunk_ids == ()
            continue
        assert item.expected_material_ids or item.expected_chunk_ids
        if item.expected_material_ids:
            assert item.expected_source_refs
        for ref in item.expected_source_refs:
            assert ref["chunk_id"].startswith("b")
            assert isinstance(ref["book"], int)
            assert isinstance(ref["chapter"], int)
        for chunk_id in item.expected_chunk_ids:
            assert chunk_id.startswith("b")


def test_lesson_fixture_does_not_store_material_prose():
    text = (FIXTURES / "lesson.jsonl").read_text(encoding="utf-8")
    assert '"quote"' not in text
    assert '"text"' not in text


def test_multiturn_fixture_has_the_expected_conversations():
    conversations = load_conversations(FIXTURES / "multiturn.jsonl")
    assert len(conversations) == 17
    assert sum(len(conversation.turns) for conversation in conversations) == 36
    assert Counter(conversation.slice_name for conversation in conversations) == {
        "same_subject_comparison": 8,
        "third_topic": 2,
        "pronoun": 1,
        "implicit_referent": 1,
        "correction": 1,
        "off_topic": 1,
        "cross_subject": 3,
    }


def test_cross_subject_turns_expect_a_referral_target():
    conversations = load_conversations(FIXTURES / "multiturn.jsonl")
    referrals = [
        turn
        for conversation in conversations
        if conversation.slice_name == "cross_subject"
        for turn in conversation.turns
        if turn.expected_referral_subject is not None
    ]
    assert len(referrals) == 3
    assert {turn.expected_referral_subject for turn in referrals} == {
        "charms",
        "dada",
        "herbology",
    }
    for turn in referrals:
        assert turn.expected_referral_concept
        assert turn.expected_mode == "referral"


def test_mixed_and_off_pack_items_expect_the_right_scope_and_citation():
    items = load_lesson_items(FIXTURES / "lesson.jsonl")
    mixed = next(item for item in items if item.slice_name == "mixed")
    off_pack = next(item for item in items if item.slice_name == "off_pack")
    assert mixed.expected_scope == "mixed"
    assert mixed.citation == "both"
    assert mixed.expected_material_ids
    assert mixed.expected_chunk_ids
    assert off_pack.expected_scope == "off_pack"
    assert off_pack.citation == "book"
    assert not off_pack.expected_material_ids
    assert off_pack.expected_chunk_ids


def test_multi_concept_items_have_one_group_per_concept():
    items = load_lesson_items(FIXTURES / "lesson.jsonl")
    multi = [item for item in items if item.slice_name == "multi_concept"]
    assert multi
    for item in multi:
        assert len(item.expected_groups) == 2
        assert all(group.material_ids for group in item.expected_groups)


def test_comparison_turns_have_one_group_per_side():
    conversations = load_conversations(FIXTURES / "multiturn.jsonl")
    comparison = next(
        conversation
        for conversation in conversations
        if conversation.conversation_id == "mt-dada-comparison"
    )
    second = comparison.turns[1]
    assert [group.title for group in second.expected_groups] == [
        "Boggart",
        "Dementors",
    ]
    assert all(group.material_ids for group in second.expected_groups)


def test_off_topic_turn_expects_abstention():
    conversations = load_conversations(FIXTURES / "multiturn.jsonl")
    off_topic = [
        conversation for conversation in conversations if conversation.slice_name == "off_topic"
    ]
    assert len(off_topic) == 1
    last = off_topic[0].turns[-1]
    assert last.expected_mode == "abstain"
    assert last.expected_abstained is True
