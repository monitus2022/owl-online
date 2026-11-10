"""Starter-prompt routing contract (#163).

The canonical strings live in `web/src/data/subjects.ts` (`startersFor`).
This file mirrors them string-for-string; a wording change updates both in the
same PR. The test runs the real deterministic router, with no model or
retrieval.
"""

from __future__ import annotations

import pytest

from app.agent.router import route

# The frontend subject names, in the same spelling as web/src/data/subjects.ts.
SUBJECT_NAMES = {
    "dada": "Defence Against the Dark Arts",
    "potions": "Potions",
    "transfiguration": "Transfiguration",
    "charms": "Charms",
    "herbology": "Herbology",
}

STARTERS_ON = {
    subject: [
        "Who are you?",
        f"What is {name}?",
        "Give me a practice question.",
        *(["What will be on the exam?"] if subject == "dada" else []),
    ]
    for subject, name in SUBJECT_NAMES.items()
}
STARTERS_OFF = {
    subject: [f"What is {name}?", "Give me a practice question."]
    for subject, name in SUBJECT_NAMES.items()
}


def _route(question: str, subject: str, *, persona: bool) -> dict[str, object]:
    return route({"question": question, "subject": subject}, persona=persona)


@pytest.mark.parametrize("subject", SUBJECT_NAMES)
def test_persona_on_starters_route(subject):
    name = SUBJECT_NAMES[subject]
    for prompt in STARTERS_ON[subject]:
        update = _route(prompt, subject, persona=True)
        if prompt == "Who are you?":
            expected_mode, expected_topic = "meta", "identity"
        elif prompt == f"What is {name}?":
            expected_mode, expected_topic = "meta", "subject"
        elif prompt == "Give me a practice question.":
            expected_mode, expected_topic = "practice", None
        else:
            expected_mode, expected_topic = "policy", "exam"
        assert update["mode"] == expected_mode, (
            f"{prompt!r} in {subject} routed {update['mode']}; update "
            "web/src/data/subjects.ts and tests/test_presets.py together"
        )
        if expected_topic is not None:
            assert update.get("meta_topic") == expected_topic, prompt


@pytest.mark.parametrize("subject", SUBJECT_NAMES)
def test_persona_off_starters_route(subject):
    name = SUBJECT_NAMES[subject]
    for prompt in STARTERS_OFF[subject]:
        update = _route(prompt, subject, persona=False)
        if prompt == f"What is {name}?":
            expected_mode = "answer"
        else:
            expected_mode = "practice"
        assert update["mode"] == expected_mode, (
            f"{prompt!r} in {subject} routed {update['mode']}; update "
            "web/src/data/subjects.ts and tests/test_presets.py together"
        )


@pytest.mark.parametrize("subject", SUBJECT_NAMES)
def test_off_state_never_offers_identity_or_exam(subject):
    assert "Who are you?" not in STARTERS_OFF[subject]
    assert "What will be on the exam?" not in STARTERS_OFF[subject]
    # The off-state routes document why: identity falls through to the corpus,
    # and the exam string hits the policy refusal rather than a persona reply.
    assert _route("Who are you?", subject, persona=False)["mode"] == "answer"
    assert _route("What will be on the exam?", subject, persona=False)["mode"] == "policy"
