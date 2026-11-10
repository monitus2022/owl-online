"""Structural and guard tests for the subject bank batches (#213 pattern)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.author_subject_bank as bank_authoring
from scripts.author_subject_bank import _check_prose, _longest_common_run

ROOT = Path(__file__).resolve().parents[1]
BANK_DIR = ROOT / "config" / "banks"


def test_batches_validate() -> None:
    for _subject, data in _batches():
        bank_authoring.ITEMS = data["items"]
        bank_authoring._validate_specs()


def test_longest_common_run() -> None:
    assert _longest_common_run("a b c d e", "x c d e y") == 3


def _batches() -> list[tuple[str, dict]]:
    return [
        (path.stem, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(BANK_DIR.glob("*.json"))
    ]


def test_batches_are_25_mcq_and_25_short_answers() -> None:
    for subject, data in _batches():
        items = data["items"]
        mcq = [item for item in items if item["kind"] == "mcq"]
        short = [item for item in items if item["kind"] == "short_answer"]
        assert len(mcq) == 25, subject
        assert len(short) == 25, subject


def test_item_ids_and_prompts_are_unique() -> None:
    for subject, data in _batches():
        ids = [item["item_id"] for item in data["items"]]
        prompts = [item["prompt"] for item in data["items"]]
        assert len(ids) == len(set(ids)), subject
        assert len(prompts) == len(set(prompts)), subject


def test_mcq_options_are_six_and_one_key() -> None:
    for _subject, data in _batches():
        for item in data["items"]:
            if item["kind"] != "mcq":
                continue
            options = item["options"]
            assert len(options) >= 6, item["item_id"]
            assert len({text.strip().lower() for text in options}) == len(options)
            assert 0 <= item["correct"] < len(options), item["item_id"]


def test_short_answers_have_valid_rubric_and_points() -> None:
    for _subject, data in _batches():
        for item in data["items"]:
            if item["kind"] != "short_answer":
                continue
            assert sum(marks for _, _, marks in item["rubric"]) == 8, item["item_id"]
            criteria = {criterion for criterion, _, _ in item["rubric"]}
            assert {"correctness", "completeness"} <= criteria, item["item_id"]
            assert 2 <= len(item["required_points"]) <= 3, item["item_id"]
            answer = item["model_answer"].lower()
            for point in item["required_points"]:
                assert point.lower() in answer, (item["item_id"], point)


def _spec(**overrides):
    spec = {
        "item_id": "test-mcq-001",
        "kind": "mcq",
        "prompt": "What does a potion do?",
        "options": [f"Option {index}" for index in range(6)],
        "correct": 0,
        "rationale": "A concept only.",
    }
    spec.update(overrides)
    return spec


def test_character_names_are_rejected() -> None:
    with pytest.raises(SystemExit, match="character"):
        _check_prose(_spec(prompt="Why does Hermione stir the potion?"))


def test_scene_markers_are_rejected() -> None:
    with pytest.raises(SystemExit, match="scene"):
        _check_prose(_spec(prompt="How is the potion used in the Quidditch match?"))


def test_exam_and_lesson_questions_are_rejected() -> None:
    with pytest.raises(SystemExit, match="exams or teaching"):
        _check_prose(_spec(prompt="What does the Potions exam paper test?"))


def test_concept_only_prose_is_accepted() -> None:
    _check_prose(_spec(prompt="What does a bezoar protect against?"))
