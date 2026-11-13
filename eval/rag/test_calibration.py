"""Calibration fixture and agreement tests; no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from eval.rag.calibration import (
    CalibrationItem,
    CalibrationResult,
    _evidence_prompt,
    load_calibration,
    parse_label,
    summarize_calibration,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_parse_label_accepts_json_with_prose():
    assert parse_label('{"label": "supported"}') == "supported"
    assert parse_label('The result is {"label": "partial"}.') == "partial"
    assert parse_label('{"label": "unsupported"}') == "unsupported"
    assert parse_label("no json") is None
    assert parse_label('{"label": "maybe"}') is None


def test_calibration_fixture_loads_with_proposed_labels():
    items = load_calibration(FIXTURES / "faithfulness_calibration.jsonl")
    assert len(items) == 18
    assert {item.label for item in items} == {
        "supported",
        "partial",
        "unsupported",
        "refusal",
    }
    assert {item.slice_name for item in items} == {
        "in_pack",
        "paraphrase",
        "multi_concept",
        "mixed",
        "off_pack",
    }
    assert all(item.label_source.startswith(("agent-proposed", "owner-adopted")) for item in items)
    assert all(item.answer for item in items)


def test_summarize_calibration_reports_exact_adjacent_and_refusal():
    def item(item_id: str, label: str) -> CalibrationItem:
        return CalibrationItem(
            item_id=item_id,
            slice_name="in_pack",
            question="q",
            answer="a",
            material_ids=(),
            chunk_ids=(),
            label=label,
            label_source="owner-adopted 2026-11-13",
        )

    results = [
        CalibrationResult(item("1", "supported"), "supported", binary_faithful=True),
        CalibrationResult(item("2", "partial"), "unsupported", binary_faithful=False),
        CalibrationResult(item("3", "unsupported"), "unsupported", binary_faithful=False),
        CalibrationResult(item("4", "refusal"), None, refusal_ok=True),
    ]
    report = summarize_calibration(results)
    assert report.total == 4
    assert report.judged == 3
    assert report.refusals == 1
    assert report.exact_agreement == 2 / 3
    assert report.adjacent_agreement == 1.0
    assert report.mean_absolute_error == 1 / 3
    assert report.binary_agreement == 1.0
    assert report.refusals_ok == 1
    assert report.adopted is True
    assert report.parse_failures == 0
    assert [result.item.item_id for result in report.disagreements] == ["2"]


def test_mixed_label_sources_are_not_adopted():
    def item(item_id: str, source: str) -> CalibrationItem:
        return CalibrationItem(
            item_id=item_id,
            slice_name="in_pack",
            question="q",
            answer="a",
            material_ids=(),
            chunk_ids=(),
            label="supported",
            label_source=source,
        )

    results = [
        CalibrationResult(item("1", "owner-adopted 2026-11-13"), "supported"),
        CalibrationResult(item("2", "agent-proposed; owner review required"), "supported"),
    ]
    report = summarize_calibration(results)
    assert report.adopted is False
    assert report.ok is False


def test_evidence_prompt_rejects_unresolved_ids():
    item = CalibrationItem(
        item_id="bad-material",
        slice_name="in_pack",
        question="q",
        answer="a",
        material_ids=("missing-material",),
        chunk_ids=(),
        label="supported",
        label_source="owner-adopted 2026-11-13",
    )
    with pytest.raises(ValueError, match="unresolved evidence"):
        _evidence_prompt(item, _EmptyPacks(), {})
    chunk_item = CalibrationItem(
        item_id="bad-chunk",
        slice_name="off_pack",
        question="q",
        answer="a",
        material_ids=(),
        chunk_ids=("b9-c99-9999",),
        label="supported",
        label_source="owner-adopted 2026-11-13",
    )
    with pytest.raises(ValueError, match="unresolved evidence"):
        _evidence_prompt(chunk_item, _EmptyPacks(), {})


class _EmptyPacks:
    def get(self, subject: str):
        return None
