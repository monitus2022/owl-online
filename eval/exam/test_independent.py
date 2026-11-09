"""Independent model-check tests with a scripted LLM, no network."""

from __future__ import annotations

import json

from eval.exam.fixtures import build_bank
from eval.exam.independent import (
    MCQ_SYSTEM,
    SHORT_JUDGE_SYSTEM,
    SHORT_SOLVER_SYSTEM,
    run_independent_checks,
)


class _ScriptedLlm:
    def __init__(self, *, mcq: str, short_judge: str) -> None:
        self.mcq = mcq
        self.short_judge = short_judge
        self.calls = 0

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        self.calls += 1
        if system == MCQ_SYSTEM:
            return self.mcq
        if system == SHORT_SOLVER_SYSTEM:
            return "A candidate answer."
        if system == SHORT_JUDGE_SYSTEM:
            return self.short_judge
        raise AssertionError(f"unexpected system: {system}")

    def stream(self, system: str, prompt: str, *, context=None):
        raise AssertionError("stream is not used")


def _mcq(best: str, judgements: dict[str, str]) -> str:
    return json.dumps(
        {
            "best": best,
            "option_judgements": judgements,
            "second_defensible": None,
            "reason": "Grounded.",
        }
    )


def _short(ok: bool = True, missing: list[str] | None = None) -> str:
    return json.dumps(
        {
            "golden_correct": ok,
            "golden_complete": ok,
            "missing_required_points": missing or [],
            "candidate_correct": True,
            "candidate_complete": True,
            "notes": "Checked.",
        }
    )


async def test_independent_checks_pass_on_a_good_reply() -> None:
    bank, pack, _, _ = build_bank()
    llm = _ScriptedLlm(
        mcq=_mcq(
            "A",
            {"A": "correct", "B": "false", "C": "false", "D": "false", "E": "false", "F": "false"},
        ),
        short_judge=_short(),
    )
    report = await run_independent_checks(bank, pack, llm)
    assert report.ok
    assert report.mcq_key_matches == 1
    assert report.mcq_ambiguities == 0
    assert report.short_golden_ok == 1
    assert report.short_missing_points == 0


async def test_independent_checks_flag_a_solver_mismatch_and_ambiguity() -> None:
    bank, pack, _, _ = build_bank()
    llm = _ScriptedLlm(
        mcq=_mcq(
            "B",
            {
                "A": "correct",
                "B": "correct",
                "C": "false",
                "D": "false",
                "E": "false",
                "F": "false",
            },
        ),
        short_judge=_short(),
    )
    report = await run_independent_checks(bank, pack, llm)
    assert not report.ok
    assert report.mcq_key_matches == 0
    assert report.mcq_ambiguities == 1


async def test_independent_checks_flag_a_short_golden_gap() -> None:
    bank, pack, _, _ = build_bank()
    llm = _ScriptedLlm(
        mcq=_mcq(
            "A",
            {"A": "correct", "B": "false", "C": "false", "D": "false", "E": "false", "F": "false"},
        ),
        short_judge=_short(ok=False, missing=["comic"]),
    )
    report = await run_independent_checks(bank, pack, llm)
    assert not report.ok
    assert report.short_golden_ok == 0
    assert report.short_missing_points == 1
