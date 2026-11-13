"""Calibration fixture and agreement tests; no network."""

from __future__ import annotations

from pathlib import Path

from eval.rag.calibration import (
    CalibrationItem,
    CalibrationResult,
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
    assert len(items) == 14
    assert {item.label for item in items} == {
        "supported",
        "partial",
        "unsupported",
        "refusal",
    }
    assert all("owner review required" in item.label_source for item in items)
    assert all(item.answer for item in items)


def test_summarize_calibration_reports_exact_adjacent_and_refusal():
    def item(item_id: str, label: str) -> CalibrationItem:
        return CalibrationItem(
            item_id=item_id,
            question="q",
            answer="a",
            material_ids=(),
            chunk_ids=(),
            label=label,
            label_source="test",
        )

    results = [
        CalibrationResult(item("1", "supported"), "supported"),
        CalibrationResult(item("2", "partial"), "unsupported"),
        CalibrationResult(item("3", "unsupported"), "unsupported"),
        CalibrationResult(item("4", "refusal"), None, refusal_ok=True),
    ]
    report = summarize_calibration(results)
    assert report.total == 4
    assert report.judged == 3
    assert report.refusals == 1
    assert report.exact_agreement == 2 / 3
    assert report.adjacent_agreement == 1.0
    assert report.mean_absolute_error == 1 / 3
    assert report.parse_failures == 0
    assert [result.item.item_id for result in report.disagreements] == ["2"]
