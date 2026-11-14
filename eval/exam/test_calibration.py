"""Short-answer calibration tests with a scripted judge, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.exam.calibration import (
    load_calibration,
    run_calibration,
    run_calibration_repeated,
)
from eval.exam.fixtures import build_bank


class _ScriptedLlm:
    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        if not self.answers:
            raise AssertionError("unexpected judge call")
        return self.answers.pop(0)

    def stream(self, system: str, prompt: str, *, context=None):
        raise AssertionError("stream is not used")


def _judge_json(item_id: str, correctness: int, completeness: int) -> str:
    return json.dumps(
        {
            "results": {
                item_id: {
                    "criteria": [
                        {
                            "criterion_id": "correctness",
                            "awarded": correctness,
                            "max_marks": 4,
                            "reason": "Correctness.",
                        },
                        {
                            "criterion_id": "completeness",
                            "awarded": completeness,
                            "max_marks": 4,
                            "reason": "Completeness.",
                        },
                    ],
                    "total": correctness + completeness,
                    "feedback": "Assessed against the rubric.",
                    "evidence_ids": ["b3-c07-0001"],
                }
            }
        }
    )


def _case(
    variant: str,
    pass_name: str,
    answer: str,
    correctness: int,
    completeness: int,
) -> dict:
    return {
        "item_id": "dada-short-001",
        "variant": variant,
        "pass": pass_name,
        "answer": answer,
        "marks": {"correctness": correctness, "completeness": completeness},
    }


def _write(path: Path, cases: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8"
    )
    return path


async def test_calibration_metrics(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration(bank, cases, llm, set_sha256="test")
    assert report.ok
    assert report.n == 3
    assert report.exact == 1.0
    assert report.adjacent == 1.0
    assert report.mae == 0.0
    assert report.per_criterion == {"correctness": 1.0, "completeness": 1.0}
    assert report.calls == 3
    assert report.passes == 3
    assert report.retries == 0
    assert report.needs_review == 0


async def test_repeated_calibration_gates_on_the_median(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 3),
        _judge_json("dada-short-001", 0, 0),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 2, 2),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration_repeated(
        bank, cases, llm, repeats=3, set_sha256="test"
    )
    assert report.repeats == 3
    assert len(report.runs) == 3
    assert report.representative_run == 3
    assert report.calls == 9
    assert report.passes == 9
    assert report.exact == pytest.approx(2 / 3)
    assert report.adjacent == pytest.approx(1.0)
    assert report.mae == pytest.approx(1 / 3)
    assert report.ok
    assert [
        (run.exact, run.adjacent, run.mae) for run in report.runs
    ] == [
        (pytest.approx(1.0), pytest.approx(1.0), pytest.approx(0.0)),
        (pytest.approx(2 / 3), pytest.approx(2 / 3), pytest.approx(2 / 3)),
        (pytest.approx(2 / 3), pytest.approx(1.0), pytest.approx(1 / 3)),
    ]

    with pytest.raises(ValueError):
        await run_calibration_repeated(bank, cases, llm, repeats=0)


async def test_repeated_calibration_fails_if_any_run_needs_review(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
        "not json",
        "still not json",
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration_repeated(
        bank, cases, llm, repeats=3, set_sha256="test"
    )
    assert report.repeats == 3
    assert report.needs_review == 1
    assert any(not run.ok for run in report.runs)
    assert not report.ok


async def test_calibration_counts_a_retry(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        "not json",
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.calls == 4
    assert report.passes == 3
    assert report.retries == 1
    assert report.ok


async def test_calibration_needs_review_is_not_ok(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        "not json",
        "still not json",
        _judge_json("dada-short-001", 3, 2),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.needs_review == 1
    assert not report.ok
    assert report.details[0].judge is None


async def test_calibration_reports_verbosity_bias(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "Short answer.", 4, 4),
            _case("verbose", "verbose", "A much longer answer with more words.", 4, 4),
            _case("partial", "partial", "Partial answer.", 3, 2),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 3, 2),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.verbose_delta == 0.0


async def test_calibration_word_count_correlation_uses_each_answer(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "Short.", 4, 4),
            _case(
                "partial",
                "partial",
                "A much longer partial answer with several more words.",
                3,
                2,
            ),
            _case("wrong", "wrong", "No.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.word_count_correlation is not None
    assert report.word_count_correlation > 0.5


async def test_calibration_fails_when_mae_and_adjacent_miss(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 0, 0),
        _judge_json("dada-short-001", 0, 0),
        _judge_json("dada-short-001", 0, 0),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.adjacent < 0.9
    assert report.mae is not None and report.mae > 1.5
    assert not report.ok


async def test_calibration_marks_must_match_the_rubric(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    bad = _case("full", "full", "A full answer.", 4, 4)
    bad["marks"] = {"correctness": 4}
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            bad,
            _case("partial", "partial", "A partial answer.", 3, 2),
            _case("wrong", "wrong", "A wrong answer.", 0, 0),
        ],
    )
    cases = load_calibration(path, min_items=1)
    with pytest.raises(ValueError, match="marks must name exactly"):
        await run_calibration(bank, cases, _ScriptedLlm())


def test_mid_band_sets_carry_a_defensible_mid_band_case() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    for subject in ("transfiguration", "herbology"):
        cases = load_calibration(fixtures / f"calibration-{subject}.jsonl")
        mid = [case for case in cases if case.variant == "partial_mid"]
        assert mid, f"{subject} has no mid-band case"
        assert all(
            case.marks == {"correctness": 4, "completeness": 2} for case in mid
        )
        # A mid-band case must sit on an item that already has a full answer,
        # so it tests completeness rather than a missing item.
        items_with_full = {case.item_id for case in cases if case.variant == "full"}
        assert {case.item_id for case in mid} <= items_with_full


async def test_mid_band_failure_does_not_fail_the_gate(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 4, 0),
            _case("partial_mid", "partial_mid", "A mid-band answer.", 4, 2),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 0),
    )
    report = await run_calibration(bank, cases, llm)
    assert report.ok
    assert report.gated.n == 2
    assert report.gated.adjacent == 1.0
    assert report.mid_band.n == 1
    assert report.mid_band.adjacent == 0.0
    assert not report.mid_band.ok


async def test_mid_band_parse_failure_still_fails_the_gate(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 4, 0),
            _case("partial_mid", "partial_mid", "A mid-band answer.", 4, 2),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 0),
        "not json",
        "still not json",
    )
    report = await run_calibration(bank, cases, llm)
    assert report.gated.ok
    assert report.mid_band.needs_review == 1
    assert not report.ok


async def test_repeated_calibration_aggregates_the_mid_band_slice(tmp_path) -> None:
    bank, _, _, _ = build_bank()
    path = _write(
        tmp_path / "calibration.jsonl",
        [
            _case("full", "full", "A full answer.", 4, 4),
            _case("partial", "partial", "A partial answer.", 4, 0),
            _case("partial_mid", "partial_mid", "A mid-band answer.", 4, 2),
        ],
    )
    cases = load_calibration(path, min_items=1)
    llm = _ScriptedLlm(
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 4),
        _judge_json("dada-short-001", 4, 0),
        _judge_json("dada-short-001", 4, 0),
    )
    report = await run_calibration_repeated(
        bank, cases, llm, repeats=3, set_sha256="test"
    )
    assert report.ok
    assert report.gated.n == 2
    assert report.gated.adjacent == 1.0
    assert report.mid_band.n == 1
    assert report.mid_band.exact == 0.0
    assert report.mid_band.adjacent == 0.0
    assert report.mid_band.mae == pytest.approx(2.0)
    assert all(run.mid_band.n == 1 for run in report.runs)
