"""Five-card persona conformance fixture (#222).

The lesson conformance case lives in ``test_charms_conformance.py``. This test
covers the card-only routes for every subject: identity, subject definition,
professor background, scope and the exam refusal. It uses the fixture's
``subject`` field and the registry card, so a copy-paste mistake in one card is
a test failure.
"""

from __future__ import annotations

from pathlib import Path

from app.agent.persona import PERSONAS
from app.agent.router import classify, contract_decision
from eval.persona.fixtures import load_persona_scenarios

FIXTURE = Path(__file__).parent / "fixtures" / "subjects.jsonl"


def test_each_card_answers_its_own_routes():
    scenarios = load_persona_scenarios(FIXTURE)
    assert len(scenarios) == 25
    assert {scenario.subject for scenario in scenarios} == set(PERSONAS)
    for scenario in scenarios:
        card = PERSONAS[scenario.subject]
        decision = contract_decision(
            scenario.question,
            subject=scenario.subject,
            requested_mode="lesson",
            teaching_terms=set(),
        )
        route = classify(
            scenario.question,
            requested_mode="lesson",
            persona=True,
            subject=scenario.subject,
            teaching_terms=set(),
        )
        assert route == scenario.route, scenario.scenario_id
        expected_contract = "persona" if scenario.route == "meta" else "policy"
        assert decision.contract == expected_contract, scenario.scenario_id
        if scenario.route == "meta":
            topic = decision.meta_topic or scenario.topic
            assert topic == scenario.topic, scenario.scenario_id
            answer = card.meta_response(topic, choice=0)
            assert answer is not None
            assert answer in card.meta[topic], scenario.scenario_id
            if topic == "identity":
                assert card.address in answer, scenario.scenario_id
                for other in PERSONAS.values():
                    if other.name != card.name:
                        assert other.address not in answer, scenario.scenario_id
                        assert other.name not in answer, scenario.scenario_id
            if topic == "subject":
                assert card.subject.lower() in answer.lower(), scenario.scenario_id
            if topic == "scope":
                assert card.subject.lower() in answer.lower(), scenario.scenario_id
        if scenario.route == "policy":
            topic = decision.meta_topic or "exam"
            answer = card.meta_response(topic, choice=0)
            assert answer is not None
            assert answer in card.meta[topic], scenario.scenario_id
            lowered = answer.lower()
            assert "examination" in lowered or "will not" in lowered or "do not" in lowered
