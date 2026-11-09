"""Router fixture: the chat intents classify correctly and overrides win."""

import pytest

from app.agent.router import classify, meta_topic, route


@pytest.mark.parametrize(
    ("question", "student_answer", "expected"),
    [
        ("What is the name of the three-headed dog?", None, "answer"),
        ("Who is the Head of Gryffindor House?", None, "answer"),
        ("What is the score of the Quidditch match?", None, "answer"),
        ("What score did the student get?", None, "answer"),
        ("Mark the date of the battle", None, "answer"),
        ("Grade boundaries for O.W.L.s?", None, "answer"),
        ("Give me the score of the match", None, "answer"),
        ("I need a grade for Potions", None, "answer"),
        ("Explain the rules of Quidditch", None, "answer"),
        ("What questions did Harry ask?", None, "answer"),
        ("Generate five exam questions on Horcruxes", None, "practice"),
        ("Write a quiz about the Triwizard Tournament", None, "practice"),
        ("Create a revision worksheet on potions", None, "practice"),
        ("Design a mock test for chapter four", None, "practice"),
        ("Give me a practice question on the Unforgivable Curses", None, "practice"),
        ("Ask me a question about the Marauder's Map", None, "practice"),
        ("Quiz me on Horcruxes", None, "practice"),
        ("Test my knowledge of defensive spells", None, "practice"),
        ("Grade this answer: Harry used Expelliarmus.", None, "feedback"),
        ("Mark the student's response out of ten", None, "feedback"),
        ("Score this answer out of 10", None, "feedback"),
        ("Assess the essay", None, "feedback"),
        ("Give me feedback on my answer", None, "feedback"),
        ("I need an assessment of this answer", None, "feedback"),
        ("I need a grade for this answer", None, "feedback"),
        ("Can you grade this answer?", None, "feedback"),
        ("Any question", "Harry used Expelliarmus.", "feedback"),
    ],
)
def test_router_fixture(question, student_answer, expected):
    assert classify(question, student_answer=student_answer) == expected


def test_explicit_mode_wins():
    assert classify("What is a Horcrux?", requested_mode="practice") == "practice"
    assert classify("Generate a quiz", requested_mode="answer") == "answer"


def test_lesson_is_an_answer_path_hint():
    assert classify("What is a Boggart?", requested_mode="lesson") == "lesson"
    assert (
        classify("Who are you?", requested_mode="lesson", persona=True) == "meta"
    )
    assert (
        classify("Give me a practice question", requested_mode="lesson")
        == "practice"
    )
    assert (
        classify(
            "Grade this answer: Harry used Expelliarmus.",
            requested_mode="lesson",
        )
        == "feedback"
    )
    assert (
        classify("How are you feeling today?", requested_mode="lesson", persona=True)
        == "lesson"
    )
    assert (
        classify(
            "I feel stressed about the exam.",
            requested_mode="lesson",
            persona=True,
        )
        == "personal"
    )
    assert classify("Who are you?", requested_mode="lesson", persona=False) == "lesson"


def test_route_returns_a_state_update():
    state = {"question": "Who is the Head of Gryffindor House?"}
    assert route(state) == {"mode": "answer"}


@pytest.mark.parametrize(
    "question",
    [
        "Who is Professor Alistair Crane?",
        "Who is Professor Crane?",
        "Who is Alistair Crane?",
        "Who is Profesor Alister Crane?",
        "Who is Proffesor Alistair Crain?",
        "Who's Crane?",
    ],
)
def test_professor_name_variants_route_to_identity(question):
    assert classify(question, persona=True) == "meta"
    assert meta_topic(question) == "identity"


@pytest.mark.parametrize(
    "question",
    [
        "Tell me about Professor Crane",
        "Tell me about Prof. Cran",
        "What is Professor Crane's background?",
        "Professor Crane's story",
    ],
)
def test_professor_background_variants_route_to_professor(question):
    assert classify(question, persona=True) == "meta"
    assert meta_topic(question) == "professor"


def test_book_professors_and_persona_off_stay_on_the_answer_path():
    assert classify("Who is Professor Snape?", persona=True) == "answer"
    assert classify("Who is Professor Crane?", persona=False) == "answer"


def test_possessive_professor_questions_stay_on_the_answer_path():
    assert classify("Tell me about Professor Crane's assistant", persona=True) == "answer"
    assert classify("Who is Professor Crane's assistant?", persona=True) == "answer"
    assert classify("Tell me about cranes", persona=True) == "answer"


@pytest.mark.parametrize(
    "question",
    [
        "Tell me about Professor Snape's background",
        "Who is Professor McGonagall?",
        "Who is Professor Lupin?",
        "Who teaches Defense Against the Dark Arts?",
    ],
)
def test_book_questions_stay_on_the_answer_path(question):
    assert classify(question, persona=True) == "answer"


def test_book_context_does_not_override_persona_identity():
    # The books do not contain Crane; a setting question about him stays meta.
    assert classify("In the books, who is Professor Crane?", persona=True) == "meta"
    assert meta_topic("In the books, who is Professor Crane?") == "identity"


def test_professor_background_needs_persona():
    assert classify("Tell me about Professor Crane", persona=False) == "answer"


def test_persona_card_name_drives_the_identity_cue():
    from app.agent.persona import PERSONA

    assert classify(f"Who is {PERSONA.name}?", persona=True) == "meta"
    assert meta_topic(f"Who is {PERSONA.name}?") == "identity"
    assert classify(f"Tell me about {PERSONA.name}", persona=True) == "meta"
    assert meta_topic(f"Tell me about {PERSONA.name}") == "professor"
