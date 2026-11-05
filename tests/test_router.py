"""Router fixture: the three chat intents classify correctly and overrides win."""

import pytest

from app.agent.router import classify, route


@pytest.mark.parametrize(
    ("question", "student_answer", "expected"),
    [
        ("What is the name of the three-headed dog?", None, "answer"),
        ("Who is the Head of Gryffindor House?", None, "answer"),
        ("What is the score of the Quidditch match?", None, "answer"),
        ("What score did the student get?", None, "answer"),
        ("Mark the date of the battle", None, "answer"),
        ("Grade boundaries for O.W.L.s?", None, "answer"),
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
        ("Can you grade this answer?", None, "feedback"),
        ("Any question", "Harry used Expelliarmus.", "feedback"),
    ],
)
def test_router_fixture(question, student_answer, expected):
    assert classify(question, student_answer=student_answer) == expected


def test_explicit_mode_wins():
    assert classify("What is a Horcrux?", requested_mode="practice") == "practice"
    assert classify("Generate a quiz", requested_mode="answer") == "answer"


def test_route_returns_a_state_update():
    state = {"question": "Who is the Head of Gryffindor House?"}
    assert route(state) == {"mode": "answer"}
