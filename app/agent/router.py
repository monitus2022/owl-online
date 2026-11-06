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
# Persona meta cues. Keep them narrow: "who teaches Defense" is an answer
# question, not an identity question.
_META_CUES: dict[str, re.Pattern[str]] = {
    "identity": re.compile(
        r"\b(who are you|what(?:'s| is) your name|introduce yourself)\b",
        re.IGNORECASE,
    ),
    "scope": re.compile(
        r"\b(what subjects? do you teach|what do you teach|which subjects? do you)\b",
        re.IGNORECASE,
    ),
    "exam": re.compile(
        r"\b(exam(?:ination)? format|what(?:'s| is) on the exam|"
        r"how is the exam (?:graded|marked)|grading scale)\b",
        re.IGNORECASE,
    ),
    "school": re.compile(
        r"\b(what school|where is (?:this|the) school|tell me about the school)\b",
        re.IGNORECASE,
    ),
    "professor": re.compile(
        r"\b(your background|were you an auror|tell me about yourself|"
        r"your experience)\b",
        re.IGNORECASE,
    ),
    "auror": re.compile(
        r"\b(how do i become an auror|auror requirements?|become an auror)\b",
        re.IGNORECASE,
    ),
}
_PERSONAL = re.compile(
    r"\b(i feel|i am (?:stressed|worried|anxious|sad|tired)|i failed|"
    r"can i talk to you|my (?:day|life|family))\b",
    re.IGNORECASE,
)


def meta_topic(question: str) -> str | None:
    """The first persona meta topic the question matches, if any."""
    for topic, pattern in _META_CUES.items():
        if pattern.search(question):
            return topic
    return None


def classify(
    question: str,
    *,
    requested_mode: RequestedMode = "auto",
    student_answer: str | None = None,
    persona: bool = False,
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
    if persona:
        if meta_topic(question) is not None:
            return "meta"
        if _PERSONAL.search(question):
            return "personal"
    return "answer"


def route(state: AgentState, *, persona: bool = False) -> dict[str, object]:
    question = state["question"]
    mode = classify(
        question,
        requested_mode=state.get("requested_mode", "auto"),
        student_answer=state.get("student_answer"),
        persona=persona,
    )
    payload: dict[str, object] = {"mode": mode}
    if mode == "meta":
        payload["meta_topic"] = meta_topic(question) or "identity"
    tracer = current_tracer()
    if tracer is not None:
        tracer.emit(
            "router",
            intent=mode,
            requested=state.get("requested_mode", "auto"),
            question_chars=len(question),
        )
    return payload
