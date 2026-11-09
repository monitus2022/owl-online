"""Judge parsing, Wilson interval and calibration aggregation, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.persona import PERSONA
from eval.persona.calibration import (
    CalibrationCase,
    load_calibration,
    run_calibration,
)
from eval.persona.judge import judge_reply, parse_score, wilson_lower_bound


class StubJudge:
    name = "stub/judge"

    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies

    async def generate(self, system, prompt, *, context=None):
        for needle, reply in self.replies.items():
            if needle in prompt:
                return reply
        return '{"score": 0, "reason": "no match"}'


def test_parse_score_accepts_json_and_prose():
    assert parse_score('{"score": 2, "reason": "good"}') == (2, "good")
    assert parse_score('Here: {"score": 1, "reason": "partial"} done') == (
        1,
        "partial",
    )
    assert parse_score('{"score": 3}') == (None, "")
    assert parse_score("not json") == (None, "")


def test_wilson_lower_bound_is_conservative():
    assert wilson_lower_bound(0, 0) == 0.0
    assert 0.0 < wilson_lower_bound(10, 10) < 1.0
    assert wilson_lower_bound(5, 10) < 0.5
    assert wilson_lower_bound(10, 10) > wilson_lower_bound(5, 10)


@pytest.mark.asyncio
async def test_judge_reply_parses_a_stub():
    judge = StubJudge({"Answer:": '{"score": 2, "reason": "in voice"}'})
    verdict = await judge_reply(
        judge,
        question="What is a Boggart?",
        answer="Answer: it is a shape-shifter.",
        anchors="direct answer first",
        persona=PERSONA,
    )
    assert verdict.score == 2
    assert verdict.reason == "in voice"
    assert not verdict.parse_failed


def test_load_calibration_fixture():
    cases = load_calibration(
        Path(__file__).parent / "fixtures" / "calibration.jsonl"
    )
    assert len(cases) == 10
    assert {case.human_score for case in cases} == {0, 1, 2}
    assert all(case.label_source == "ai-proposed" for case in cases)


@pytest.mark.asyncio
async def test_calibration_aggregation():
    cases = [
        CalibrationCase("c1", "q1", "a1", 2, "shape", "", "ai-proposed"),
        CalibrationCase("c2", "q2", "a2", 1, "shape", "", "ai-proposed"),
        CalibrationCase("c3", "q3", "a3", 0, "shape", "", "ai-proposed"),
    ]
    judge = StubJudge(
        {
            "q1": '{"score": 2, "reason": "full"}',
            "q2": '{"score": 1, "reason": "partial"}',
            "q3": '{"score": 0, "reason": "none"}',
        }
    )
    report = await run_calibration(cases, judge, persona=PERSONA)
    assert report.n == 3
    assert report.exact == 1.0
    assert report.adjacent == 1.0
    assert report.mae == 0.0
    assert report.ok
