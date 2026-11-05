"""Judge prompts for the practice/feedback routing comparison."""

from __future__ import annotations

from typing import Any

from eval.harness.judging import _as_bool, _first_json_object

PRACTICE_JUDGE_SYSTEM = (
    "You grade a practice question generated for a revision chat. Use only the "
    "excerpts provided. Reply with JSON only: "
    '{"on_topic": bool, "grounded": bool, "answerable": bool, '
    '"boundary": bool}. on_topic means it addresses the request; grounded means '
    "the question and its answer are supported by the excerpts; answerable means "
    "a student could answer it from the excerpts; boundary means it stays "
    "conversational practice rather than claiming to be a formal exam."
)

FEEDBACK_JUDGE_SYSTEM = (
    "You grade formative feedback on a student answer. Use only the excerpts and "
    "the reference answer. Reply with JSON only: "
    '{"band": "strong" | "partial" | "wrong", "error_named": bool, '
    '"grounded": bool, "boundary": bool}. band is the quality of the student '
    "answer as the feedback describes it; error_named means the feedback names "
    "the specific mistake when one exists; grounded means the feedback is "
    "supported by the excerpts; boundary means it stays formative and does not "
    "claim to be an official score."
)


def parse_routing_verdict(raw: str, intent: str) -> dict[str, Any] | None:
    data = _first_json_object(raw)
    if data is None:
        return None
    if intent == "practice":
        if "on_topic" not in data:
            return None
        return {
            "on_topic": _as_bool(data.get("on_topic")),
            "grounded": _as_bool(data.get("grounded")),
            "answerable": _as_bool(data.get("answerable")),
            "boundary": _as_bool(data.get("boundary")),
        }
    band = str(data.get("band", "")).lower()
    if band not in {"strong", "partial", "wrong"}:
        return None
    return {
        "band": band,
        "error_named": _as_bool(data.get("error_named")),
        "grounded": _as_bool(data.get("grounded")),
        "boundary": _as_bool(data.get("boundary")),
    }
