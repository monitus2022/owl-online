"""Structural tests for the Charms bank authoring batch (#213).

The bank prose and evidence stay in the gitignored data tree, so CI cannot
validate the published bank. These checks run without corpus data and catch a
malformed batch before it reaches the pack/corpus validator.
"""

from __future__ import annotations

from collections import Counter

import pytest

from scripts.author_charms_bank import ITEMS, _check_prose, _validate_specs


def test_batch_has_25_mcq_and_25_short_answers() -> None:
    kinds = Counter(spec["kind"] for spec in ITEMS)
    assert kinds == {"mcq": 25, "short_answer": 25}


def test_batch_validates() -> None:
    _validate_specs()


def test_mcq_options_are_unique_and_six_long() -> None:
    for spec in ITEMS:
        if spec["kind"] != "mcq":
            continue
        options = [text.strip().lower() for text in spec["options"]]
        assert len(options) >= 6, spec["item_id"]
        assert len(set(options)) == len(options), spec["item_id"]
        assert not {"all of the above", "none of the above"} & set(options)


def test_short_answer_rubrics_sum_to_eight() -> None:
    for spec in ITEMS:
        if spec["kind"] != "short_answer":
            continue
        marks = sum(mark for _, _, mark in spec["rubric"])
        assert marks == 8, spec["item_id"]
        criteria = {criterion for criterion, _, _ in spec["rubric"]}
        assert {"correctness", "completeness"} <= criteria, spec["item_id"]


def test_short_answers_have_two_or_three_required_points() -> None:
    for spec in ITEMS:
        if spec["kind"] != "short_answer":
            continue
        points = spec["required_points"]
        assert 2 <= len(points) <= 3, spec["item_id"]
        assert all(point.strip() for point in points), spec["item_id"]


def test_item_ids_are_unique_across_kinds() -> None:
    ids = [spec["item_id"] for spec in ITEMS]
    assert len(ids) == len(set(ids))


def _spec(**overrides):
    spec = {
        "item_id": "charms-test",
        "kind": "mcq",
        "prompt": "What does a charm change?",
        "difficulty": "recall",
        "options": [f"Option {index}" for index in range(6)],
        "correct": 0,
        "rationale": "The concept only.",
    }
    spec.update(overrides)
    return spec


def test_character_names_are_rejected() -> None:
    with pytest.raises(SystemExit, match="character"):
        _check_prose(_spec(prompt="Why does Hermione correct Ron?"))


def test_scene_markers_are_rejected() -> None:
    with pytest.raises(SystemExit, match="scene"):
        _check_prose(_spec(prompt="How is the charm used in the Quidditch match?"))


def test_concept_only_prose_is_accepted() -> None:
    _check_prose(_spec(prompt="What does the Banishing Charm do to a target?"))
