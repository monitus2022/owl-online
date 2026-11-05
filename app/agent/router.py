"""Deterministic chat-intent router: answer | practice | feedback.

These are chat intents, not product modes. Practice is an ephemeral, grounded
question or two. Feedback is formative and provisional. The formal exam bank is
a separate offline pipeline with stored mark schemes and deterministic scoring.
"""

import re

from app.agent.state import AgentState, Mode, RequestedMode
from app.trace import current_tracer

_FEEDBACK_ACTION = re.compile(
    r"^\s*(please\s+)?(grade|mark|score|assess|evaluate)\b",
    re.IGNORECASE,
)
_FEEDBACK_ASK = re.compile(
    r"\b(can|could|would|will)\s+you\s+(please\s+)?"
    r"(grade|mark|score|assess|evaluate)\b",
    re.IGNORECASE,
)
_FEEDBACK_TARGET = re.compile(
    r"\b(answer|response|essay|work|student|script|submission|"
    r"following|this|it)\b",
    re.IGNORECASE,
)
_FEEDBACK_REQUEST = re.compile(
    r"\b(give|provide|send|need|want)\b[^.?!]*\bfeedback\b",
    re.IGNORECASE,
)
_FEEDBACK_NOUN_REQUEST = re.compile(
    r"\b(give|provide|send|need|want)\b[^.?!]*\b"
    r"(assessment|grade|mark|score)\b",
    re.IGNORECASE,
)
_PRACTICE_REQUEST = re.compile(
    r"\b(generate|create|make|write|draft|compose|produce|build|design|"
    r"give|ask|quiz|test)\b[^.?!]*\b"
    r"(question|questions|practice|exercise|exercises|drill|drills|"
    r"quiz|quizzes|exam|exams|test|tests|worksheet|worksheets)\b",
    re.IGNORECASE,
)
_PRACTICE_PHRASE = re.compile(
    r"\b(quiz|test) (me|my knowledge)\b",
    re.IGNORECASE,
)


def classify(
    question: str,
    *,
    requested_mode: RequestedMode = "auto",
    student_answer: str | None = None,
) -> Mode:
    if requested_mode != "auto":
        return requested_mode
    if student_answer and student_answer.strip():
        return "feedback"
    if _FEEDBACK_REQUEST.search(question):
        return "feedback"
    if _FEEDBACK_NOUN_REQUEST.search(question) and _FEEDBACK_TARGET.search(question):
        return "feedback"
    if _FEEDBACK_ACTION.search(question) and _FEEDBACK_TARGET.search(question):
        return "feedback"
    if _FEEDBACK_ASK.search(question) and _FEEDBACK_TARGET.search(question):
        return "feedback"
    if _PRACTICE_REQUEST.search(question) or _PRACTICE_PHRASE.search(question):
        return "practice"
    return "answer"


def route(state: AgentState) -> dict[str, str]:
    mode = classify(
        state["question"],
        requested_mode=state.get("requested_mode", "auto"),
        student_answer=state.get("student_answer"),
    )
    tracer = current_tracer()
    if tracer is not None:
        tracer.emit(
            "router",
            intent=mode,
            requested=state.get("requested_mode", "auto"),
            question_chars=len(state["question"]),
        )
    return {"mode": mode}
