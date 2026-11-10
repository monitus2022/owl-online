"""Deterministic chat-intent router.

Intents: answer | practice | feedback | meta | personal | lesson.

These are chat intents, not product modes. Practice is an ephemeral, grounded
question or two. Feedback is formative and provisional. The formal exam bank is
a separate offline pipeline with stored mark schemes and deterministic scoring.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.agent.persona import PERSONA, PERSONAS, Persona
from app.agent.state import AgentState, Mode, RequestedMode
from app.knowledge.terms import content_terms
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
    r"moody|umbridge|snape|carrow|crouch|tonks|o\.?w\.?l\.?)\b",
    re.IGNORECASE,
)
_SUBJECT_NAME = (
    r"(?:dada|defence against the dark arts|defense against the dark arts|"
    r"defence against dark arts|defense against dark arts)"
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
        r"what is on the test|what is (?:the )?(?:.* )?exam"
        r"(?: (?:format|contents|date|schedule))?(?=\s*[?.!]*\s*$))\b",
        re.IGNORECASE,
    ),
    "syllabus": re.compile(
        r"\b(what is (?:the )?(?:.* )?syllabus|course outline|curriculum|"
        r"what will we cover|what does the course cover)\b",
        re.IGNORECASE,
    ),
    "subject": re.compile(
        rf"^\s*(?:"
        rf"what(?:'s| is) (?:the )?{_SUBJECT_NAME}(?: (?:subject|department|class))?"
        rf"|what does {_SUBJECT_NAME} (?:mean|stand for)"
        rf"|what(?:'s| is) {_SUBJECT_NAME} short for"
        rf"|(?:define|explain) (?:the )?{_SUBJECT_NAME}"
        rf"|what(?:'s| is) (?:the )?meaning of {_SUBJECT_NAME}"
        rf"|(?:the )?meaning of {_SUBJECT_NAME}"
        rf"|{_SUBJECT_NAME} meaning"
        rf"|tell me about (?:the )?{_SUBJECT_NAME}"
        rf"|what is (?:this|your) (?:subject|class|department)"
        rf"|what (?:subject|class|department) is this"
        rf"|{_SUBJECT_NAME}"
        rf")\s*[?.!]*\s*$",
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


POLICY_TOPICS = frozenset({"exam", "syllabus", "grading"})
_POLICY_NEAR = re.compile(
    r"\b(exam paper|test paper|mark scheme|marking scheme|assessment key|"
    r"answer key|model answer|examiner|invigilator|grade boundaries|pass mark|"
    r"what will (?:i|we) be tested on|what will you test|"
    r"how will .* (?:graded|marked)|what is on the test|what is on the exam|"
    r"assessment)\b",
    re.IGNORECASE,
)
_POLICY_PATTERNS = (
    re.compile(
        r"\b(exam|examination|test(?:ed|ing)?|assessment|paper|examin(?:ed|able))\b"
        r".*\b(what|how|when|which|format|question|topic|date|long|many|"
        r"pass|score|mark|grade|prediction|examiner|invigilator|answer|key|"
        r"scheme|criteria|rubric|boundary|cut-off|outstanding|essay|practical|"
        r"guidance|setter|board|come up)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(what|how|when|which|tell|show|give|can|could|will)\b.*"
        r"\b(exam|examination|test(?:ed|ing)?|assessment|paper|examin(?:ed|able))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(syllabus|assessment|mark scheme|marking scheme|answer key|model answer|"
        r"examiner|invigilators?|grade boundaries|pass mark|cut-off|assessable|"
        r"examinable|scoring rule|marking criteria|grading rubric|exam board|"
        r"exam setter|exam answers|O and (?:an? )?E|panel.*grade|grade.*panel)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(ignore|override|reveal|pretend)\b.*"
        r"\b(instructions|rules|prompt|exam|paper|answers|mark scheme)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(you are the exam setter|system prompt|mark my exam|before i sit|"
        r"questions? (?:will )?come up|what will .* ask|"
        r"what topics will be examined|format of the practical|practical format|"
        r"marks?.*(?:essay|short answers?|paper|question))\b",
        re.IGNORECASE,
    ),
)

_POLICY_NEGATIVE = re.compile(
    r"\b(exam room|exam hall|test whether|test if|test for|paper bird|"
    r"paper trail|paper plane|paper aeroplane)\b",
    re.IGNORECASE,
)
_OFF_TOPIC = re.compile(
    r"\b(bake bread|pizza|weather|capital of|meaning of life|tell me a joke|"
    r"stock price|fix my car|write my essay|favourite colour|girlfriend|"
    r"dream last night|password to my email|breakfast|football team|"
    r"professor's cat|stop taking my medicine|medical advice|legal advice|"
    r"dangerous potion at home|make a dangerous potion)\b",
    re.IGNORECASE,
)
_DADA_ONLY = re.compile(
    r"\b(professor crane|alistair crane|dada|defence against the dark arts|"
    r"defense against the dark arts)\b",
    re.IGNORECASE,
)

_SCOPE_AMBIGUOUS = re.compile(
    r"\b(what is included in|what is on the .* course|what does .* involve|"
    r"what does the .* course include|what is the .* course about|"
    r"what is the .* course)\b",
    re.IGNORECASE,
)
_SCHOOL_AMBIGUOUS = re.compile(
    r"\b(tell me about (?:the|your) (?:old )?school|which school are you from|"
    r"what is your school)\b",
    re.IGNORECASE,
)
_EDUCATION = re.compile(
    r"\b(where did you (?:study|learn|go to school)|what school did you attend|"
    r"where were you educated|your education|when you were young|"
    r"where did you study|which academy did you attend|in your youth|"
    r"when you were a lad|where did you learn magic|did you go to|"
    r"study at hogwarts|train as a young wizard|where did you train)\b",
    re.IGNORECASE,
)
_TEACHING_RECORD = re.compile(
    r"\b(set texts|teaching record|policy on the set texts)\b", re.IGNORECASE
)
_SCHOOL = re.compile(
    r"\b(ashcombe|the school|this school|the academy|founders? of ashcombe|"
    r"who founded|when was ashcombe founded|where is ashcombe|"
    r"how many students|house system|five departments|school's history|"
    r"school's founding|departments does ashcombe)\b",
    re.IGNORECASE,
)
_AUROR = re.compile(
    r"\b(auror office|become an auror|auror pathway|auror training|"
    r"post-war scheme|ministry's post-war)\b",
    re.IGNORECASE,
)
_TIMELINE_1998 = re.compile(r"\b(1998|battle of hogwarts)\b", re.IGNORECASE)
_TIMELINE_2008 = re.compile(r"\b2008\b")
_TIMELINE_2026 = re.compile(r"\b2026\b|present year", re.IGNORECASE)
_PUBLIC_RECORD = re.compile(
    r"\b(public record|public-record|people in the books|private knowledge)\b",
    re.IGNORECASE,
)
_SUBJECT_SCOPE = re.compile(
    r"\b(what does .* cover|what topics are in|what is the .* curriculum|"
    r"what is the .* department|what is the .* department's focus|"
    r"what does .* department (?:specialise|focus)|"
    r"what is the defense department|is .* compulsory|"
    r"where does practical work)\b",
    re.IGNORECASE,
)
_IDENTITY = re.compile(
    r"\b(who are you|what(?:'s| is) your name|introduce yourself|"
    r"who am i speaking to)\b",
    re.IGNORECASE,
)
_BACKGROUND = re.compile(
    r"\b(your background|tell me about yourself|your experience|your story|"
    r"were you an auror|how long were you in the auror office|"
    r"why did you leave the aurors|after the war|what did you do after)\b",
    re.IGNORECASE,
)
_SCOPE = re.compile(
    r"\b(what is your subject|what subjects do you teach|what do you teach|"
    r"what is your field)\b",
    re.IGNORECASE,
)
_BOUNDARIES = re.compile(
    r"\b(what can i ask you|what are your limits|what will you not answer)\b",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^\s*(hello|hi|good morning|good evening|good afternoon)"
    r"(?:,\s*(?:professor|prof\.?))?[.!]?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContractDecision:
    """The answer contract the router selects before retrieval."""

    contract: str
    meta_topic: str | None = None
    fact_ids: tuple[str, ...] = ()
    reason: str = ""


def _policy_topic(question: str) -> str:
    topic = meta_topic(question)
    if topic in POLICY_TOPICS:
        return topic
    if re.search(r"\b(syllabus|curriculum|assessment)\b", question, re.IGNORECASE):
        return "syllabus"
    if re.search(r"\b(grade|mark|score|examiner|invigilator)\b", question, re.IGNORECASE):
        return "grading"
    return "exam"


def _subject_terms(subject: str) -> str:
    card = PERSONAS.get(subject)
    if card is None:
        return ""
    if subject == "dada":
        return _SUBJECT_NAME
    return re.escape(card.subject.lower())


def _mentions_subject(question: str, subject: str) -> bool:
    terms = _subject_terms(subject)
    return bool(terms and re.search(rf"\b{terms}\b", question, re.IGNORECASE))


def _subject_definition(question: str, subject: str) -> bool:
    terms = _subject_terms(subject)
    if not terms:
        return False
    return bool(
        re.search(
            rf"^\s*(?:what is|what's) (?:the )?{terms}\s*[?.!]*\s*$|"
            rf"^\s*(?:what does|what's) {terms} mean\s*[?.!]*\s*$|"
            rf"^\s*(?:define|explain) (?:the )?{terms}\s*[?.!]*\s*$|"
            rf"^\s*(?:the )?meaning of {terms}\s*[?.!]*\s*$",
            question,
            re.IGNORECASE,
        )
    )

def _name_topic(question: str, card: Persona) -> str | None:
    names = "|".join(
        re.escape(name) for name in (card.address.lower(), card.name.lower())
    )
    if re.search(rf"(?:{names})(?![\w-])(?!['’]s\b)", question, re.IGNORECASE) is None:
        return None
    if re.search(r"\b(who is|who's|are you)\b", question, re.IGNORECASE):
        return "identity"
    if re.search(
        r"\b(tell me about|background|story|experience)\b", question, re.IGNORECASE
    ):
        return "professor"
    return None


def contract_decision(
    question: str,
    *,
    subject: str = "dada",
    requested_mode: str = "auto",
    teaching_terms: set[str] | None = None,
) -> ContractDecision:
    """The policy, closed-fact and teaching gates, in that order."""
    card = PERSONAS.get(subject) or PERSONA
    book_context = bool(_BOOK_CONTEXT.search(question))

    if _PRACTICE_REQUEST.search(question) and re.search(
        r"\bpractice\b", question, re.IGNORECASE
    ):
        return ContractDecision("answer", reason="explicit practice request")
    if (
        _FEEDBACK_REQUEST.search(question)
        or (_FEEDBACK_NOUN_REQUEST.search(question) and _FEEDBACK_TARGET.search(question))
        or (_FEEDBACK_ASK.search(question) and _FEEDBACK_TARGET.search(question))
    ) and re.search(
        r"\b(this|my) (answer|response|work|essay|script)\b", question, re.IGNORECASE
    ):
        return ContractDecision("answer", reason="explicit feedback request")

    if re.search(
        r"\b(what does the course cover|what is on the course|"
        r"what will you teach me|what does the course include|"
        r"what is the course about|what does the department (?:actually )?"
        r"(?:put in front|cover|include))\b",
        question,
        re.IGNORECASE,
    ):
        return ContractDecision("clarify", reason="course scope or assessment")
    if re.search(r"\bcompare .* (?:levitation|summoning) charm\b", question, re.IGNORECASE):
        return ContractDecision("clarify", reason="cross-subject comparison")
    if re.search(
        r"\b(what did you study|what do you teach|what is your field)\b",
        question,
        re.IGNORECASE,
    ):
        return ContractDecision("clarify", reason="study or teaching role")

    if re.search(r"\bcurriculum\b", question, re.IGNORECASE):
        if book_context:
            return ContractDecision(
                "lesson" if requested_mode == "lesson" else "answer",
                reason="book context",
            )
        if _mentions_subject(question, subject):
            if subject == "dada":
                return ContractDecision("lore", fact_ids=("lore:dada-001",))
            return ContractDecision(
            "persona", meta_topic="subject", fact_ids=("persona:subject",)
        )
        return ContractDecision("clarify", reason="curriculum scope or assessment")

    topic = meta_topic(question)
    if topic in POLICY_TOPICS and not (topic == "syllabus" and book_context):
        return ContractDecision("policy", meta_topic=topic)
    if (
        any(p.search(question) for p in _POLICY_PATTERNS)
        and not _POLICY_NEGATIVE.search(question)
        and (
            not book_context
            or re.search(
                r"\b(exam|examination|test|graded|mark scheme|examiner|"
                r"invigilator|answer key|model answer|ignore|override|"
                r"system prompt)\b",
                question,
                re.IGNORECASE,
            )
        )
    ):
        return ContractDecision("policy", meta_topic=_policy_topic(question))

    # Closed setting facts run before the book-context guard: a persona
    # education question or a school-history question is not a book question.
    if _EDUCATION.search(question):
        return ContractDecision(
            "persona",
            meta_topic="professor",
            fact_ids=("persona:professor.education",),
        )
    if _TEACHING_RECORD.search(question):
        return ContractDecision("lore", fact_ids=("lore:teaching-record",))
    if re.search(
        r"\b(were you an auror|how long were you in the auror office|"
        r"why did you leave the aurors|your auror service)\b",
        question,
        re.IGNORECASE,
    ):
        return ContractDecision(
            "persona",
            meta_topic="professor",
            fact_ids=("persona:professor.background",),
        )
    if _AUROR.search(question):
        if book_context:
            return ContractDecision(
                "lesson" if requested_mode == "lesson" else "answer",
                reason="book character",
            )
        return ContractDecision("lore", fact_ids=("lore:auror-001",))
    if _TIMELINE_1998.search(question):
        return ContractDecision("lore", fact_ids=("lore:timeline-1998",))
    if _TIMELINE_2008.search(question):
        return ContractDecision("lore", fact_ids=("lore:timeline-2008",))
    if _TIMELINE_2026.search(question):
        return ContractDecision("lore", fact_ids=("lore:timeline-2026",))
    if re.search(r"\btimeline of the school\b", question, re.IGNORECASE):
        return ContractDecision(
            "lore",
            fact_ids=(
                "lore:timeline-1998",
                "lore:timeline-2008",
                "lore:timeline-2026",
            ),
        )
    if re.search(
        r"\bpublic-record limit|private knowledge|memory is not evidence\b",
        question,
        re.IGNORECASE,
    ):
        return ContractDecision("lore", fact_ids=("lore:public-record-limits",))
    if re.search(r"\bpeople in the books|public figures\b", question, re.IGNORECASE):
        return ContractDecision("lore", fact_ids=("lore:public-record-people",))
    if _PUBLIC_RECORD.search(question):
        return ContractDecision("lore", fact_ids=("lore:public-record-war",))
    if _SCHOOL.search(question):
        if _OFF_TOPIC.search(question):
            return ContractDecision(
                "abstain" if requested_mode == "lesson" else "answer",
                reason="off topic",
            )
        if book_context:
            return ContractDecision(
                "lesson" if requested_mode == "lesson" else "answer",
                reason="book context",
            )
        return ContractDecision("lore", fact_ids=("lore:school-001",))
    if subject == "dada" and re.search(
        r"\b(defense|defence) department|practical work|training room\b",
        question,
        re.IGNORECASE
    ):
        return ContractDecision("lore", fact_ids=("lore:dada-001",))

    if book_context:
        return ContractDecision(
            "lesson" if requested_mode == "lesson" else "answer",
            reason="book context",
        )
    if subject != "dada" and _DADA_ONLY.search(question):
        return ContractDecision(
            "abstain" if requested_mode == "lesson" else "answer",
            reason="cross-subject",
        )

    if _SCHOOL_AMBIGUOUS.search(question) or _SCOPE_AMBIGUOUS.search(question):
        return ContractDecision("clarify", reason="scope or assessment")
    if _SUBJECT_SCOPE.search(question) and _mentions_subject(question, subject):
        if subject == "dada":
            return ContractDecision("lore", fact_ids=("lore:dada-001",))
        return ContractDecision(
            "persona", meta_topic="subject", fact_ids=("persona:subject",)
        )
    if _subject_definition(question, subject):
        return ContractDecision(
            "persona", meta_topic="subject", fact_ids=("persona:subject",)
        )

    name_topic = _name_topic(question, card)
    if name_topic is not None:
        return ContractDecision(
            "persona", meta_topic=name_topic,
            fact_ids=(
                "persona:identity"
                if name_topic == "identity"
                else "persona:professor.background",
            ),
        )
    if _IDENTITY.search(question):
        return ContractDecision(
            "persona", meta_topic="identity", fact_ids=("persona:identity",)
        )
    if _BACKGROUND.search(question):
        return ContractDecision(
            "persona", meta_topic="professor",
            fact_ids=("persona:professor.background",),
        )
    if _SCOPE.search(question):
        return ContractDecision(
            "persona", meta_topic="scope", fact_ids=("persona:subject",)
        )
    if _BOUNDARIES.search(question):
        return ContractDecision(
            "persona", meta_topic="boundaries", fact_ids=("persona:boundaries",)
        )
    if _GREETING.search(question):
        return ContractDecision(
            "persona", meta_topic="greeting", fact_ids=("persona:greeting",)
        )

    if _OFF_TOPIC.search(question):
        return ContractDecision(
            "abstain" if requested_mode == "lesson" else "answer",
            reason="off topic",
        )

    if requested_mode == "lesson":
        if teaching_terms is not None:
            if content_terms(question) & teaching_terms:
                return ContractDecision("lesson")
            return ContractDecision("abstain", reason="no teaching term")
        return ContractDecision("lesson")
    return ContractDecision("answer")

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
            topic in {"exam", "syllabus", "subject"} and _BOOK_CONTEXT.search(question)
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
    subject: str = "dada",
    teaching_terms: set[str] | None = None,
) -> Mode:
    auto = _auto_mode(
        question, student_answer=student_answer, persona=persona
    )
    decision = contract_decision(
        question,
        subject=subject,
        requested_mode=requested_mode,
        teaching_terms=teaching_terms,
    )
    if decision.contract == "policy":
        return "policy"
    if persona and decision.contract == "persona":
        return "meta"
    if decision.contract == "lore":
        return "fact"
    if decision.contract == "clarify":
        return "clarify"
    if decision.contract == "abstain":
        return "abstain"
    if requested_mode in ("answer", "practice", "feedback"):
        return requested_mode
    if auto in ("practice", "feedback", "personal"):
        return auto
    if persona and auto == "meta":
        return "meta"
    if requested_mode == "lesson":
        return "lesson"
    if requested_mode != "auto":
        return requested_mode
    return auto


def route(
    state: AgentState,
    *,
    persona: bool = False,
    teaching_terms: Callable[[str], set[str]] | None = None,
) -> dict[str, object]:
    question = state["question"]
    subject = state.get("subject", "dada")
    requested = state.get("requested_mode", "auto")
    terms = teaching_terms(subject) if teaching_terms is not None else None
    mode = classify(
        question,
        requested_mode=requested,
        student_answer=state.get("student_answer"),
        persona=persona and state.get("persona_enabled", True),
        subject=subject,
        teaching_terms=terms,
    )
    payload: dict[str, object] = {"mode": mode}
    if mode in ("meta", "policy", "fact", "clarify", "abstain"):
        decision = contract_decision(
            question,
            subject=subject,
            requested_mode=requested,
            teaching_terms=terms,
        )
        if mode in ("meta", "policy"):
            payload["meta_topic"] = (
                decision.meta_topic or meta_topic(question) or "identity"
            )
        if mode == "fact":
            payload["fact_ids"] = list(decision.fact_ids)
    tracer = current_tracer()
    if tracer is not None:
        tracer.emit(
            "router",
            intent=mode,
            requested=state.get("requested_mode", "auto"),
            question_chars=len(question),
        )
    return payload
