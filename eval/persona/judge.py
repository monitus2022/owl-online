"""Pinned judge for persona voice and teaching shape.

The judge sees the question and the answer only. It never sees the condition,
so the baseline/candidate comparison is blind. It scores voice and shape, not
facts or citations: the deterministic checks own those.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from app.agent.persona import Persona
from app.providers.contracts import Llm
from eval.persona.fixtures import PersonaScenario

PROMPT_VERSION = "persona-voice-v1"

JUDGE_SYSTEM = (
    "You review a teaching answer for voice and teaching shape only. Do not "
    "grade factual accuracy or citations; a separate deterministic check owns "
    "those. Ignore bracketed citation markers entirely when judging voice. "
    "The persona is Professor Alistair Crane, a Defense Against the "
    "Dark Arts professor. Register: friendly yet formal, warm, patient and "
    "precise; never chummy, no slang, no emojis. Stance: Defense is serious and "
    "dangerous; caution and correct technique come before action. No deadlines "
    "or countdowns; the student sets the pace. A conforming answer speaks to "
    "the student as the professor, answers directly first, says why the point "
    "matters, gives one concrete example, adds one caution, finishes with one "
    "short check the student can answer, and stays within a few short "
    "paragraphs. Reply with JSON only, no prose: "
    '{"score": 0 | 1 | 2, "reason": "one sentence"}. '
    "2 = fully conforms. 1 = partly conforms, for example grounded and clear "
    "but third-person, encyclopedic, or missing most of the teaching shape. "
    "0 = does not conform: generic assistant or encyclopedia voice, slang, "
    "emoji, deadline, or a boundary violation."
)


@dataclass(frozen=True)
class JudgeVerdict:
    scenario_id: str
    score: int | None
    reason: str
    parse_failed: bool

    @property
    def passed(self) -> bool:
        return self.score == 2


def _first_json_object(raw: str) -> dict[str, object] | None:
    match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_score(raw: str) -> tuple[int | None, str]:
    """Pull a 0-2 score and reason from a judge reply; tolerate prose."""
    data = _first_json_object(raw)
    if data is None:
        return None, ""
    value = data.get("score")
    if isinstance(value, bool):
        return None, ""
    try:
        score = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None, ""
    if score not in (0, 1, 2):
        return None, ""
    reason = data.get("reason", "")
    return score, str(reason).strip()


async def judge_reply(
    judge: Llm,
    *,
    question: str,
    answer: str,
    anchors: str,
    persona: Persona,
) -> JudgeVerdict:
    """One judge call; the condition is never passed to the judge."""
    prompt = (
        f"Persona: {persona.address}, {persona.role}.\n"
        f"Question: {question}\n"
        f"Anchors for this scenario: {anchors}.\n\n"
        f"Answer:\n{answer}"
    )
    raw = await judge.generate(JUDGE_SYSTEM, prompt)
    score, reason = parse_score(raw)
    return JudgeVerdict(
        scenario_id="",
        score=score,
        reason=reason,
        parse_failed=score is None,
    )


async def judge_answer(
    judge: Llm,
    scenario: PersonaScenario,
    answer: str,
    *,
    persona: Persona,
) -> JudgeVerdict:
    """One judge call for a fixture scenario."""
    anchors = "; ".join(scenario.anchors) or "the teaching shape"
    verdict = await judge_reply(
        judge,
        question=scenario.question,
        answer=answer,
        anchors=anchors,
        persona=persona,
    )
    return JudgeVerdict(
        scenario_id=scenario.scenario_id,
        score=verdict.score,
        reason=verdict.reason,
        parse_failed=verdict.parse_failed,
    )


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    """The lower bound of the Wilson score interval for a binomial rate."""
    if n <= 0:
        return 0.0
    p = successes / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - spread) / denominator)


__all__ = [
    "JUDGE_SYSTEM",
    "PROMPT_VERSION",
    "JudgeVerdict",
    "judge_answer",
    "parse_score",
    "wilson_lower_bound",
]
