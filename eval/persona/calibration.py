"""Judge calibration for the persona-voice rubric.

Ten reviewed examples span the three score bands. The labels are proposed from
the rubric and adopted by the owner in review, the same pattern the exam
calibration fixture uses. The report records exact and adjacent agreement and
the mean absolute error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.agent.persona import Persona
from app.providers.contracts import Llm
from eval.persona.judge import judge_reply


@dataclass(frozen=True)
class CalibrationCase:
    case_id: str
    question: str
    answer: str
    human_score: int
    anchors: str
    note: str
    label_source: str


@dataclass(frozen=True)
class CalibrationDetail:
    case_id: str
    human: int
    judge: int | None
    delta: int | None
    reason: str


@dataclass(frozen=True)
class CalibrationReport:
    n: int
    exact: float
    adjacent: float
    mae: float
    parse_failures: int
    details: tuple[CalibrationDetail, ...]
    labels_adopted: bool = False

    @property
    def ok(self) -> bool:
        return (
            self.n > 0
            and self.labels_adopted
            and self.parse_failures == 0
            and self.adjacent >= 0.9
            and self.mae <= 0.5
        )


def _score(record: dict[str, object], where: str) -> int:
    value = record.get("human_score")
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2):
        raise ValueError(f"{where}: human_score must be 0, 1 or 2")
    return value


def load_calibration(path: Path) -> list[CalibrationCase]:
    cases: list[CalibrationCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path}:{line_number}"
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{where}: invalid JSON: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{where}: each line must be an object")
        case_id = str(record.get("case_id", "")).strip()
        question = str(record.get("question", "")).strip()
        answer = str(record.get("answer", "")).strip()
        if not case_id or not question or not answer:
            raise ValueError(f"{where}: case_id, question and answer are required")
        if case_id in seen:
            raise ValueError(f"{where}: duplicate case_id {case_id!r}")
        seen.add(case_id)
        cases.append(
            CalibrationCase(
                case_id=case_id,
                question=question,
                answer=answer,
                human_score=_score(record, where),
                anchors=str(record.get("anchors", "the teaching shape")).strip(),
                note=str(record.get("note", "")).strip(),
                label_source=str(record.get("label_source", "ai-proposed")).strip(),
            )
        )
    if not cases:
        raise ValueError(f"{path}: no calibration cases")
    return cases


async def run_calibration(
    cases: list[CalibrationCase],
    judge: Llm,
    *,
    persona: Persona,
) -> CalibrationReport:
    details: list[CalibrationDetail] = []
    parse_failures = 0
    exact = 0
    adjacent = 0
    total_delta = 0
    scored = 0
    for case in cases:
        verdict = await judge_reply(
            judge,
            question=case.question,
            answer=case.answer,
            anchors=case.anchors,
            persona=persona,
        )
        if verdict.score is None:
            parse_failures += 1
            details.append(
                CalibrationDetail(case.case_id, case.human_score, None, None, verdict.reason)
            )
            continue
        delta = abs(verdict.score - case.human_score)
        exact += int(delta == 0)
        adjacent += int(delta <= 1)
        total_delta += delta
        scored += 1
        details.append(
            CalibrationDetail(
                case.case_id, case.human_score, verdict.score, delta, verdict.reason
            )
        )
    n = len(cases)
    return CalibrationReport(
        n=n,
        exact=exact / n if n else 0.0,
        adjacent=adjacent / n if n else 0.0,
        mae=total_delta / scored if scored else 0.0,
        parse_failures=parse_failures,
        details=tuple(details),
        labels_adopted=all(
            case.label_source == "owner-adopted" for case in cases
        ),
    )


__all__ = [
    "CalibrationCase",
    "CalibrationDetail",
    "CalibrationReport",
    "load_calibration",
    "run_calibration",
]
