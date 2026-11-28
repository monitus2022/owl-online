"""Deterministic chat-intent router.

Intents: answer | practice | feedback | meta | personal | lesson.

These are chat intents, not product modes. Practice is an ephemeral, grounded
question or two. Feedback is formative and provisional. The formal exam bank is
a separate offline pipeline with stored mark schemes and deterministic scoring.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.agent.intent import Candidate, ResidualClassifier
from app.agent.persona import PERSONA, PERSONAS, Persona
from app.agent.state import AgentState, Mode, RequestedMode
from app.knowledge.lore import BOOK_CONTEXT as _BOOK_CONTEXT
from app.knowledge.lore import LoreStore
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
    r"following|this)\b",
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
    r"give|quiz|test|ask me)\b[^.?!]*\b"
    r"(question|questions|practice|exercise|exercises|drill|drills|"
    r"quiz|quizzes|exam|exams|test|tests|worksheet|worksheets)\b",
    re.IGNORECASE,
)
_PRACTICE_PHRASE = re.compile(
    r"\b(quiz|test) (me|my knowledge)\b",
    re.IGNORECASE,
)
# Explicit practice requests keep their route even when the wording mentions an
# exam. The quantifier keeps "give me the exam format" on the policy path.
_PRACTICE_EXEMPT = re.compile(
    r"\b(generate|create|make|write|draft|compose|produce|build|design)\b"
    r"[^.?!]*\b(practice|exercises?|drills?|quiz|quizzes|worksheets?)\b"
    r"|\b(generate|create|make|give)\b[^.?!]*\b"
    r"(?:a|an|some|one|two|three|four|five|\d+)\b[^.?!]*\bquestions?\b"
    r"|\bask me\b[^.?!]*\bquestions?\b"
    r"|\bgive me (?:a|an|some) practice (?:test|exam|paper)\b"
    r"(?!\s+(?:format|contents?|schedule|date))"
    r"|\bquiz (?:me|my knowledge)\b",
    re.IGNORECASE,
)
# A request for the format of a practice exam/test/paper is a policy question,
# not a practice request. A practice request that merely mentions the format as
# a topic ("questions about the format") is still practice.
_PRACTICE_FORMAT_GUARD = re.compile(
    r"\b(?:give me\s+)?(?:a\s+|an\s+|some\s+)?practice\s+"
    r"(?:exam|test|paper)\s+(?:questions?\s+)?"
    r"(?:formats?|contents?|schedules?|dates?)\b",
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
_POLICY_PATTERNS = (
    re.compile(
        r"\b(exams?|examinations?|test(?:s|ed|ing)?|assessments?|papers?|examin(?:ed|able))\b"
        r".*\b(what|how|when|which|format|question|topic|date|long|many|"
        r"pass|score|mark|grade|prediction|examiner|invigilator|answer|key|"
        r"scheme|criteria|rubric|boundary|cut-off|outstanding|essay|practical|"
        r"guidance|setter|board|come up)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(what|how|when|which|tell|show|give|can|could|will)\b.*"
        r"\b(exams?|examinations?|test(?:s|ed|ing)?|assessments?|papers?|examin(?:ed|able))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(syllabus|assessments?|mark schemes?|marking schemes?|answer keys?|model answers?|"
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
    re.compile(
        r"\b(did|do|will|would|can|could) you "
        r"(?:go|going|sit|take|see|attend) "
        r"(?:to |for )?(?:the )?(?:\w+ )?(?:exam|test|assessment)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(did|do|will|would|can|could) you (?:study|learn|train)\b.*"
        r"\b(?:exams?|tests?|assessments?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ask|tell|show|give) me (?:about|on) (?:the )?"
        r"(?:exams?|examinations?|tests?|assessments?|papers?)\b",
        re.IGNORECASE,
    ),
)

_POLICY_NEGATIVE = re.compile(
    r"\b(exam room|exam hall|test whether|test if|test for|paper bird|"
    r"paper trail|paper plane|paper aeroplane)\b",
    re.IGNORECASE,
)
_OFF_TOPIC = re.compile(
    r"\b(bake bread|the best pizza|the weather tomorrow|capital of "
    r"(?:france|germany|spain|italy|america|the united states)|meaning of life|"
    r"tell me a joke|stock price|fix my car|write my essay|favourite colour|"
    r"do you have a girlfriend|dream last night|password to my email|"
    r"professor[\w' ]* breakfast|favourite quidditch team|football team|"
    r"professor's cat|stop taking my medicine|give me legal advice|"
    r"legal advice about|sue my neigh?bour|dangerous potion at home|"
    r"password to the .*common room|privately thinks|private opinion)\b",
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
    r"\b(tell me about (?:the|your|this) (?:old )?(?:school|academy)|"
    r"which school are you from|what is your school|what is this school|"
    r"which school is this)\b",
    re.IGNORECASE,
)
_EDUCATION = re.compile(
    r"\b(where did you (?:study|learn|go to school)|what school did you attend|"
    r"where were you educated|your education|when you were young|"
    r"where did you study|which academy did you attend|in your youth|"
    r"when you were a lad|where did you learn magic|"
    r"did you go to (?:hogwarts|school|the school|a wizarding school)|"
    r"did you (?:study|learn|train) (?:at|in) "
    r"(?:hogwarts|school|the school|a wizarding school)|"
    r"did you attend (?:hogwarts|school|the school)|"
    r"were you (?:a student )?at hogwarts|"
    r"have you studied (?:at|in) hogwarts|"
    r"study at hogwarts|train as a young wizard|"
    r"where did you train (?:as a (?:young )?(?:wizard|witch)|in magic))\b",
    re.IGNORECASE,
)
_EXAM_WORDS = re.compile(
    r"\b(exam(?:ination)?s?|test(?:s|ed|ing)?|assessment(?:s)?|"
    r"paper(?:s)?|mark scheme)\b|(?<![a-z])o\.?w\.?l\.?(?![a-z])",
    re.IGNORECASE,
)
_TEACHING_RECORD = re.compile(
    r"\b(set texts|teaching record|policy on the set texts)\b", re.IGNORECASE
)
_SCHOOL = re.compile(
    r"\b(ashcombe|the school|this school|school'?s|the academy|this academy|"
    r"the campus|this place|this building|"
    r"what kind of school|what sort of school|where am i|where are we|"
    r"where exactly am i|"
    r"founders? of ashcombe|who founded|when was ashcombe founded|"
    r"when was it founded|where is ashcombe|how many students|"
    r"house system|what houses|does this school have houses|"
    r"five departments|what departments|which departments|"
    r"how many departments|who are the founders|who were the founders|"
    r"five founders|the five founders|"
    r"departments does ashcombe|school'?s history|school'?s founding|"
    r"headmaster|headmistress|leads the school|"
    r"who is in charge here|who is in charge of (?:this|the) (?:school|academy)|"
    r"who runs this place|student body|the faculty)\b",
    re.IGNORECASE,
)
_AUROR = re.compile(
    r"\b(auror office|become an auror|auror pathway|auror training|"
    r"post-war scheme|ministry's post-war)\b",
    re.IGNORECASE,
)
_TIMELINE_1998 = re.compile(r"\b(1998|battle of hogwarts)\b", re.IGNORECASE)
_TIMELINE_2008 = re.compile(r"\b2008\b")
_TIMELINE_2026 = re.compile(
    r"\b2026\b|present year|current year|what year is it|what is the year",
    re.IGNORECASE,
)
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
    r"what do you cover|what is your field)\b",
    re.IGNORECASE,
)
_BOUNDARIES = re.compile(
    r"\b(what can i ask you|what are your limits|what will you not answer)\b",
    re.IGNORECASE,
)
_GREETING = re.compile(
    r"^\s*(hello|hi|hey|good morning|good evening|good afternoon)"
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
    if re.search(r"\b(syllabus|curriculum|assessments?)\b", question, re.IGNORECASE):
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

    if _PRACTICE_EXEMPT.search(question) and not _PRACTICE_FORMAT_GUARD.search(
        question
    ):
        return ContractDecision("answer", reason="explicit practice request")
    if (
        _FEEDBACK_REQUEST.search(question)
        or (_FEEDBACK_NOUN_REQUEST.search(question) and _FEEDBACK_TARGET.search(question))
        or (_FEEDBACK_ACTION.search(question) and _FEEDBACK_TARGET.search(question))
        or (_FEEDBACK_ASK.search(question) and _FEEDBACK_TARGET.search(question))
    ):
        return ContractDecision("answer", reason="explicit feedback request")

    # A setting question and an assessment question in the same turn cannot be
    # answered by either contract. Ask one short question instead of letting the
    # policy gate swallow the setting half. The book-context guard keeps a
    # Hogwarts exam question on the book path.
    if (
        (
            _EXAM_WORDS.search(question)
            or re.search(
                r"\b(syllabus|grading|grade|mark scheme|marking)\b",
                question,
                re.IGNORECASE,
            )
        )
        and not book_context
        and not _EDUCATION.search(question)
        and (
            _SCHOOL.search(question)
            or _TIMELINE_1998.search(question)
            or _TIMELINE_2008.search(question)
            or _TIMELINE_2026.search(question)
            or _AUROR.search(question)
            or _TEACHING_RECORD.search(question)
        )
    ):
        return ContractDecision("clarify", reason="setting and assessment")

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
        if _EXAM_WORDS.search(question):
            return ContractDecision("policy", meta_topic=_policy_topic(question))
        return ContractDecision(
            "persona",
            meta_topic="professor",
            fact_ids=("persona:professor.education",),
        )
    if _TEACHING_RECORD.search(question):
        return ContractDecision("lore", fact_ids=("lore:teaching-record",))
    if re.search(
        r"\b(were you an auror|how long were you in the auror office|"
        r"why did you leave the aurors|your auror service|"
        r"where did you train as an auror|did you train as an auror)\b",
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
    subject: str = "dada",
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
        topic = meta_topic(question) if subject == "dada" else None
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
        question,
        student_answer=student_answer,
        persona=persona,
        subject=subject,
    )
    decision = contract_decision(
        question,
        subject=subject,
        requested_mode=requested_mode,
        teaching_terms=teaching_terms,
    )
    if decision.contract == "policy":
        return "policy"
    if decision.contract == "persona":
        if persona and decision.fact_ids == ("persona:professor.education",):
            return "fact"
        if persona:
            return "meta"
    if decision.contract == "lore":
        return "fact"
    if decision.contract == "clarify":
        return "clarify"
    if requested_mode in ("answer", "practice", "feedback"):
        return requested_mode
    if auto in ("practice", "feedback", "personal"):
        return auto
    if persona and auto == "meta":
        return "meta"
    if decision.contract == "abstain":
        return "abstain"
    if requested_mode == "lesson":
        return "lesson"
    if requested_mode != "auto":
        return requested_mode
    return auto


# A weak lexical signal is only evidence when the question itself points at the
# setting: a deictic ("this", "here"), the speaker ("I", "we"), or a setting
# word. Without one, a lore label on a book definition such as "What is a
# Boggart?" has nothing to stand on.
_WEAK_SETTING = re.compile(
    r"\b(this|these|here|there|our|we|us|i|my|academy|ashcombe|school|"
    r"campus|building|place|auror|professor|faculty|founder|department|"
    r"student|headmaster|headmistress|year|staff|subject|people)\b",
    re.IGNORECASE,
)
# A persona label needs a second-person or professor cue. "Who is in charge
# here?" is a setting question, not an identity question, even though both are
# "who" questions.
_PERSONA_CUE = re.compile(
    r"\b(you|your|yours|yourself|professor|crane|vale|hale|raman|ashby|"
    r"background|story|experience|study|studied|education|teach|teaches|"
    r"teaching|subject)\b",
    re.IGNORECASE,
)
_POLICY_CUE = re.compile(
    r"\b(exam(?:ination)?s?|test(?:s|ed|ing)?|assessment(?:s)?|"
    r"syllabus|grade[ds]?|grading|mark(?:s|ing)?|mark scheme|paper(?:s)?)\b",
    re.IGNORECASE,
)


def _persona_topic(question: str) -> str:
    if re.search(
        r"\b(background|story|experience|study|studied|education|auror|"
        r"where did|where were)\b",
        question,
        re.IGNORECASE,
    ):
        return "professor"
    if re.search(
        r"\b(subject|teach|teaching|department|cover|cover(s|ed)?)\b",
        question,
        re.IGNORECASE,
    ):
        return "subject"
    if re.search(
        r"\b(can you|limits?|will you not|what do you cover|help with)\b",
        question,
        re.IGNORECASE,
    ):
        return "boundaries"
    return "identity"


def _lore_evidence(
    lore: LoreStore | None,
    question: str,
    subject: str,
    entry_id: str,
    previous: str = "",
) -> bool:
    """The named entry must exist, match the room, and beat the runner-up.

    An empty ranked list is the paraphrase case: no entry shares a word with
    the question, so the model's semantic link is the only evidence available
    and existence plus subject is enough. A weak single-token hit is treated the
    same way. Anything stronger must agree with the choice and leave a margin,
    because `fact_node` returns the body verbatim with no later verification.
    """
    if lore is None:
        return False
    entry = lore.get(entry_id)
    if entry is None or entry.subject not in (subject, "all"):
        return False
    # A book question that mentions a school is still a book question. The
    # previous turn is context for a fragment, never for the entry score.
    context = f"{previous} {question}".strip()
    if _BOOK_CONTEXT.search(context):
        return False
    # Score across every room: the runner-up should be the strongest alternative
    # anywhere in the pack, not only in this room, so a room entry cannot win by
    # default. The candidate's subject is checked separately above.
    ranked = lore.ranked(question)
    scores = {candidate.id: score for score, candidate in ranked}
    if entry_id not in scores:
        return (
            not ranked or ranked[0][0] <= 1
        ) and bool(_WEAK_SETTING.search(context))
    runner_up = max(
        (score for score, candidate in ranked if candidate.id != entry_id),
        default=0,
    )
    return scores[entry_id] > runner_up


def _persona_evidence(
    personas: dict[str, Persona] | None,
    subject: str,
    question: str,
    previous: str = "",
) -> str | None:
    """The scripted topic the turn would use, or None when the card has none."""
    card = (personas or {}).get(subject)
    if card is None:
        return None
    if not _PERSONA_CUE.search(question) and not _PERSONA_CUE.search(previous):
        return None
    topic = _persona_topic(question)
    for candidate in (topic, "professor", "subject", "boundaries", "identity"):
        if card.meta_response(candidate):
            return candidate
    return None


def _policy_evidence(question: str, previous: str) -> bool:
    return bool(_POLICY_CUE.search(question) or _POLICY_CUE.search(previous))


def _override(
    candidate: Candidate,
    question: str,
    previous: str,
    *,
    subject: str,
    lore: LoreStore | None,
    personas: dict[str, Persona] | None,
) -> tuple[dict[str, object], int] | None:
    """The first candidate with real evidence, as a payload and its index."""
    choices = [(candidate.contract, candidate.entry_id)]
    if candidate.second_contract is not None:
        choices.append((candidate.second_contract, candidate.second_entry_id))
    for index, (contract, entry_id) in enumerate(choices):
        if contract == "lore" and entry_id:
            # The model may answer with an authored alias. Resolve to the
            # canonical id before the gate and the citation, so `fact_node` and
            # the typed citation always agree.
            entry = lore.get(entry_id) if lore is not None else None
            if entry is not None and _lore_evidence(
                lore, question, subject, entry.id, previous
            ):
                return {
                    "mode": "fact",
                    "routed_mode": "fact",
                    "fact_ids": [f"lore:{entry.id}"],
                }, index
        elif contract == "persona":
            topic = _persona_evidence(personas, subject, question, previous)
            if topic is not None:
                return {
                    "mode": "meta",
                    "routed_mode": "meta",
                    "meta_topic": topic,
                }, index
        elif contract == "policy":
            if _policy_evidence(question, previous):
                return {
                    "mode": "policy",
                    "routed_mode": "policy",
                    "meta_topic": _policy_topic(question),
                }, index
        elif contract == "clarify":
            if candidate.second_contract in {"lore", "persona", "policy"}:
                return {"mode": "clarify", "routed_mode": "clarify"}, index
    return None


def _classify_residual(
    intent: ResidualClassifier, question: str, previous: str, subject: str
) -> Candidate | None:
    """Run the classifier on its own long-lived loop, bounded by its timeout."""
    return intent.classify_sync(question, previous=previous, subject=subject)


def route(
    state: AgentState,
    *,
    persona: bool = False,
    teaching_terms: Callable[[str], set[str]] | None = None,
    intent: ResidualClassifier | None = None,
    intent_mode: str = "off",
    lore: LoreStore | None = None,
    personas: dict[str, Persona] | None = None,
) -> dict[str, object]:
    question = state.get("standalone_question") or state["question"]
    forced = state.get("forced_mode")
    if forced:
        payload: dict[str, object] = {"mode": forced, "routed_mode": forced}
        if forced == "policy":
            payload["meta_topic"] = "exam"
        tracer = current_tracer()
        if tracer is not None:
            tracer.emit(
                "router",
                intent=forced,
                requested=state.get("requested_mode", "auto"),
                question_chars=len(question),
            )
        return payload
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
    # An elliptical follow-up in a lesson thread keeps the teaching contract,
    # but only after the policy, fact, clarify and abstain gates have run and
    # only when the client did not ask for a specific mode.
    if requested == "auto" and mode == "answer" and state.get("preferred_mode") == "lesson":
        mode = "lesson"
    payload: dict[str, object] = {"mode": mode, "routed_mode": mode}
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

    deterministic = mode
    trace_fields: dict[str, object] = {}
    if mode == "abstain" and intent is not None and intent_mode in {"shadow", "on"}:
        started = time.perf_counter()
        candidate = _classify_residual(
            intent,
            question,
            state.get("last_student_message", ""),
            subject,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        trace_fields = {
            "classifier_model": intent.model,
            "classifier_label": candidate.contract if candidate else None,
            "classifier_entry": candidate.entry_id if candidate else None,
            "classifier_second": candidate.second_contract if candidate else None,
            "classifier_ms": elapsed_ms,
            "deterministic_label": deterministic,
        }
        payload["classifier_used"] = True
        if intent_mode == "on" and candidate is not None:
            override = _override(
                candidate,
                question,
                state.get("last_student_message", ""),
                subject=subject,
                lore=lore,
                personas=personas,
            )
            if override is not None:
                payload, choice = override
                payload["classifier_used"] = True
                payload["classifier_choice"] = choice
                mode = str(payload["mode"])

    tracer = current_tracer()
    if tracer is not None:
        tracer.emit(
            "router",
            intent=mode,
            requested=state.get("requested_mode", "auto"),
            question_chars=len(question),
            **trace_fields,
        )
    return payload
