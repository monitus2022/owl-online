"""Short-term conversation memory (#30): resolver and bounded context."""

from app.agent.memory import (
    context_chars,
    extract_entity,
    resolve_followup,
    trim_history,
)


def test_extract_entity():
    assert extract_entity("Who is Professor Lupin?") == "Professor Lupin"
    assert extract_entity("What is a Boggart?") == "Boggart"
    assert extract_entity("Did you go to Hogwarts?") == "Hogwarts"
    assert extract_entity("Who trained him?") is None


def test_pronoun_followup_uses_the_last_entity():
    resolution = resolve_followup("who trained him?", last_entity="Professor Lupin")
    assert resolution.standalone == "who trained Professor Lupin?"
    assert resolution.forced_mode is None


def test_followup_recovers_the_entity_from_messages():
    resolution = resolve_followup(
        "who trained him?",
        messages=[
            {"role": "user", "content": "Who is Professor Lupin?"},
            {"role": "assistant", "content": "A professor."},
        ],
    )
    assert resolution.standalone == "who trained Professor Lupin?"


def test_followup_recovers_the_entity_from_the_summary():
    resolution = resolve_followup(
        "who trained him?",
        summary="Earlier: Who is Professor Lupin?",
    )
    assert resolution.standalone == "who trained Professor Lupin?"


def test_what_about_inherits_the_teaching_authority():
    resolution = resolve_followup("what about a Dementor?", last_mode="lesson")
    assert resolution.standalone == "What is a Dementor?"


def test_pending_clarify_consumes_the_answer():
    assert resolve_followup("the exam", pending_clarify=True).forced_mode == "policy"
    scope = resolve_followup("the topics", pending_clarify=True)
    assert "cover" in scope.standalone
    assert resolve_followup("not sure", pending_clarify=True).forced_mode == "clarify"


def test_a_new_question_is_unchanged():
    resolution = resolve_followup("What is a Boggart?")
    assert resolution.standalone == "What is a Boggart?"
    assert resolution.forced_mode is None


def test_trim_history_bounds_the_context():
    messages = [
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "y" * 1000},
    ] * 5
    kept, summary = trim_history(messages, "", window=4, token_budget=100)
    assert len(kept) <= 4
    assert context_chars(kept, summary) <= 400
    assert len(summary) <= 400
