"""Deterministic chat-intent router.

Intents: answer | practice | feedback | meta | personal | lesson.

These are chat intents, not product modes. Practice is an ephemeral, grounded
question or two. Feedback is formative and provisional. The formal exam bank is
a separate offline pipeline with stored mark schemes and deterministic scoring.
"""

import re

from app.agent.persona import PERSONA
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
# A curriculum question with a book context is a book question, not a syllabus
# question. The guard keeps "What is the DADA curriculum at Hogwarts?" on the
# answer path while "What is the DADA curriculum?" routes to the syllabus.
_BOOK_CONTEXT = re.compile(
    r"\b(hogwarts|books?|novels?|book \d|book one|book two|book three|"
    r"book four|book five|book six|book seven|first year|second year|"
    r"third year|fourth year|fifth year|sixth year|seventh year|"
    r"year (?:one|two|three|four|five|six|seven)|quirrell|lockhart|lupin|"
    r"moody|umbridge|snape|carrow|crouch)\b",
    re.IGNORECASE,
)
# Persona meta cues. Keep them narrow: "who teaches Defense" is an answer
# question, not an identity question. The name and title come from the card so
# a persona edit cannot silently break routing. The router reads the
# module-level PERSONA; per-subject cards are not wired yet.
_PERSONA_TOKENS = tuple(
    token.lower() for token in PERSONA.name.split() if token.isalpha()
)
_PERSONA_LAST = _PERSONA_TOKENS[-1]
_PERSONA_FIRST = " ".join(_PERSONA_TOKENS[:-1]) or _PERSONA_LAST
_PERSONA_TITLE = PERSONA.address.split()[0].lower()
_FIRST = re.escape(_PERSONA_FIRST)
_LAST = re.escape(_PERSONA_LAST)
_TITLE = re.escape(_PERSONA_TITLE)
_NAME = rf"(?:{_TITLE} |{_TITLE[:4]}\.? )?(?:{_FIRST} )?{_LAST}"
_META_CUES: dict[str, re.Pattern[str]] = {
    "identity": re.compile(
        rf"\b("
        rf"who are you|what(?:'s| is) your name|introduce yourself|"
        rf"who(?:'s| is| are) {_NAME}(?![\w-])(?!['’]s\b)"
        rf")\b",
        re.IGNORECASE,
    ),
    "scope": re.compile(
        r"\b(what subjects? do you teach|what do you teach|which subjects? do you)\b",
        re.IGNORECASE,
    ),
    "exam": re.compile(
        r"\b(exam(?:ination)? format|what(?:'s| is) on the exam|"
        r"what is on the test)\b",
        re.IGNORECASE,
    ),
    "syllabus": re.compile(
        r"\b(what is the syllabus|course outline|curriculum|what will we cover|"
        r"what does the course cover)\b",
        re.IGNORECASE,
    ),
    "grading": re.compile(
        r"\b(how (?:is|are) (?:the exam|the paper|answers?) (?:graded|marked)|"
        r"grading scale)\b",
        re.IGNORECASE,
    ),
    "school": re.compile(
        r"\b(what school (?:do you|is this)|where is (?:this|the) school|"
        r"tell me about the school)\b",
        re.IGNORECASE,
    ),
    "professor": re.compile(
        rf"\b("
        rf"your background|were you an auror|tell me about yourself|your experience|"
        rf"tell me about {_NAME}(?![\w-])(?!['’]s\b)|"
        rf"{_NAME}(?![\w-])(?:'s|’s)? (?:background|story|experience)|"
        rf"what (?:is|was) {_NAME}(?![\w-])(?:'s|’s)? (?:background|story)"
        rf")\b",
        re.IGNORECASE,
    ),
    "auror": re.compile(
        r"\b(how do i become an auror|what (?:are|do) (?:the )?auror "
        r"requirements?|auror requirements?)\b",
        re.IGNORECASE,
    ),
    "boundaries": re.compile(
        r"\b(what can you (?:help|do)|what do you cover|can you help with)\b",
        re.IGNORECASE,
    ),
    # Last: "Hello, who are you?" should answer the identity, not the greeting.
    "greeting": re.compile(
        r"^\s*(hi|hello|hey|good (?:morning|afternoon|evening))\s*[!.,]?\s*$",
        re.IGNORECASE,
    ),
}
_PERSONAL = re.compile(
    r"\b(i feel|i(?:'m| am) (?:stressed|worried|anxious|sad|tired)|i failed|"
    r"can i talk to you|my (?:day|life|family))\b",
    re.IGNORECASE,
)


# The professor's name is typed by hand. Normalise known spelling variants
# before the deterministic cues; only a fixed alias table is rewritten, so an
# ordinary word is never rewritten into a name.
_KNOWN_ALIASES = {
    "crane": ("crain", "craine"),
    "alistair": ("alister", "alistar"),
    "professor": ("profesor", "proffesor"),
}
_NAME_ALIASES = {
    token: (token, *_KNOWN_ALIASES.get(token, ()))
    for token in {_PERSONA_LAST, _PERSONA_FIRST, _PERSONA_TITLE}
}
_NAME_TOKEN = re.compile(r"[A-Za-z]+")


def _canonical_name(token: str) -> str:
    lowered = token.lower()
    for canonical, variants in _NAME_ALIASES.items():
        if lowered in variants:
            return canonical
    return token


def _normalise_names(question: str) -> str:
    return _NAME_TOKEN.sub(lambda match: _canonical_name(match.group(0)), question)


def meta_topic(question: str) -> str | None:
    """The first persona meta topic the question matches, if any."""
    normalised = _normalise_names(question)
    for topic, pattern in _META_CUES.items():
        if pattern.search(normalised):
            return topic
    return None


def _auto_mode(
    question: str,
    *,
    student_answer: str | None,
    persona: bool,
) -> Mode:
    """The intent without an explicit request override."""
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
        topic = meta_topic(question)
        if topic is not None and not (
            topic == "syllabus" and _BOOK_CONTEXT.search(question)
        ):
            return "meta"
        if _PERSONAL.search(question):
            return "personal"
    return "answer"


def classify(
    question: str,
    *,
    requested_mode: RequestedMode = "auto",
    student_answer: str | None = None,
    persona: bool = False,
) -> Mode:
    auto = _auto_mode(
        question, student_answer=student_answer, persona=persona
    )
    if requested_mode == "lesson":
        # Lesson is a preference for the answer path, not an absolute route:
        # persona, practice and feedback keep their normal handling, so a
        # venue that defaults to lesson still greets and tests correctly.
        return "lesson" if auto == "answer" else auto
    if requested_mode != "auto":
        return requested_mode
    return auto


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
