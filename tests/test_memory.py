"""Short-term conversation memory (#30): resolver and bounded context."""

from app.agent.memory import (
    context_chars,
    extract_entity,
    resolve_followup,
    trim_history,
)
from app.agent.router import route


def test_extract_entity():
    person = extract_entity("Who is Professor Lupin?")
    assert person is not None
    assert (person.text, person.kind) == ("Professor Lupin", "person")
    thing = extract_entity("What is a Boggart?")
    assert thing is not None
    assert (thing.text, thing.kind) == ("Boggart", "thing")
    place = extract_entity("Did you go to Hogwarts?")
    assert place is not None
    assert (place.text, place.kind) == ("Hogwarts", "place")
    assert extract_entity("Who trained him?") is None


def test_a_compound_question_keeps_the_first_entity():
    entity = extract_entity("Who is Professor Lupin and what is a Boggart?")
    assert entity is not None
    assert entity.text == "Professor Lupin"


def test_pronoun_followup_uses_the_last_person():
    resolution = resolve_followup("who trained him?", last_person="Professor Lupin")
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


def test_an_intervening_thing_does_not_replace_the_person():
    resolution = resolve_followup(
        "who trained him?",
        messages=[
            {"role": "user", "content": "Who is Professor Lupin?"},
            {"role": "assistant", "content": "A professor."},
            {"role": "user", "content": "What is a Boggart?"},
            {"role": "assistant", "content": "A shape-shifter."},
        ],
    )
    assert resolution.standalone == "who trained Professor Lupin?"


def test_a_self_reference_is_not_a_person():
    resolution = resolve_followup(
        "who trained him?",
        messages=[
            {"role": "user", "content": "Tell me about yourself."},
            {"role": "assistant", "content": "I am the professor."},
        ],
    )
    assert resolution.standalone == "who trained him?"


def test_a_lesson_pronoun_followup_keeps_the_lesson_hint():
    resolution = resolve_followup(
        "who trained him?",
        last_person="Professor Lupin",
        last_mode="lesson",
    )
    assert resolution.standalone == "who trained Professor Lupin?"
    assert resolution.preferred_mode == "lesson"


def test_what_about_inherits_the_teaching_authority():
    resolution = resolve_followup("what about a Dementor?", last_mode="lesson")
    assert resolution.standalone == "What is a Dementor?"
    assert resolution.preferred_mode == "lesson"


def test_what_about_without_a_thread_is_unchanged():
    resolution = resolve_followup("what about a Dementor?")
    assert resolution.standalone == "what about a Dementor?"
    assert resolution.preferred_mode is None


def test_existential_there_is_not_rewritten():
    resolution = resolve_followup(
        "Is there a Boggart?", last_place="Hogwarts"
    )
    assert resolution.standalone == "Is there a Boggart?"


def test_an_entity_with_a_backslash_is_literal():
    resolution = resolve_followup("who trained him?", last_person="C:\\temp")
    assert resolution.standalone == "who trained C:\\temp?"


def test_pending_clarify_consumes_the_answer():
    assert resolve_followup("the exam", pending_clarify=True).forced_mode == "policy"
    scope = resolve_followup("the topics", pending_clarify=True)
    assert "cover" in scope.standalone
    assert resolve_followup("not sure", pending_clarify=True).forced_mode == "clarify"
    assert resolve_followup("test me", pending_clarify=True).forced_mode == "practice"


def test_a_new_question_escapes_a_pending_clarify():
    resolution = resolve_followup("What is a Boggart?", pending_clarify=True)
    assert resolution.standalone == "What is a Boggart?"
    assert resolution.forced_mode is None


def test_a_new_question_is_unchanged():
    resolution = resolve_followup("What is a Boggart?")
    assert resolution.standalone == "What is a Boggart?"
    assert resolution.forced_mode is None


def test_lesson_hint_keeps_a_followup_in_lesson():
    result = route(
        {
            "question": "what about a Dementor?",
            "standalone_question": "What is a Dementor?",
            "preferred_mode": "lesson",
            "requested_mode": "auto",
            "subject": "dada",
            "persona_enabled": False,
        }
    )
    assert result["mode"] == "lesson"
    assert result["routed_mode"] == "lesson"


def test_policy_gate_beats_the_lesson_hint():
    result = route(
        {
            "question": "what about the exam?",
            "standalone_question": "What is the exam?",
            "preferred_mode": "lesson",
            "requested_mode": "auto",
            "subject": "dada",
            "persona_enabled": False,
        }
    )
    assert result["mode"] == "policy"


def test_trim_history_bounds_the_context():
    messages = [
        {"role": "user", "content": "x" * 1000},
        {"role": "assistant", "content": "y" * 1000},
    ] * 5
    kept, summary = trim_history(messages, "", window=4, token_budget=100)
    assert len(kept) <= 4
    assert context_chars(kept, summary) <= 400
    assert len(summary) <= 400
