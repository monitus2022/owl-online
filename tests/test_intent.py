"""Residual intent classifier and evidence gate tests (#327), no network."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.agent.intent import (
    Candidate,
    ResidualClassifier,
    build_system,
    parse_candidate,
)
from app.agent.persona import PERSONAS
from app.agent.router import _lore_evidence, route
from app.knowledge.lore import load_lore
from app.trace import TraceSink, end_trace, start_trace

FIXTURE = Path(__file__).parents[1] / "eval" / "fixtures" / "lore"


class SequenceLlm:
    """A fixed sequence of replies, one per call."""

    def __init__(self, replies: list[str]) -> None:
        self.name = "sequence/intent"
        self.replies = replies
        self.calls = 0

    async def generate(self, system, prompt, context=None):
        reply = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return reply

    def stream(self, system, prompt, context=None):  # pragma: no cover - contract
        raise NotImplementedError


class ScriptedLlm:
    """One fixed reply, with a call count and an optional delay."""

    def __init__(self, reply: str, *, delay: float = 0.0) -> None:
        self.name = "scripted/intent"
        self.reply = reply
        self.delay = delay
        self.calls = 0

    async def generate(self, system, prompt, context=None):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.reply

    def stream(self, system, prompt, context=None):  # pragma: no cover - contract
        raise NotImplementedError


def classifier(reply: str, *, delay: float = 0.0) -> ResidualClassifier:
    return ResidualClassifier(
        llm=ScriptedLlm(reply, delay=delay),
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
        timeout_s=0.05 if delay else 1.5,
    )


def route_state(question: str, *, previous: str = "") -> dict:
    return {
        "question": question,
        "standalone_question": question,
        "last_student_message": previous,
        "subject": "dada",
        "requested_mode": "lesson",
        "persona_enabled": True,
    }


TERMS = {"boggart", "dementor", "expelliarmus", "patronus", "curse"}


def test_parse_accepts_fenced_json_and_rejects_lesson():
    parsed = parse_candidate(
        '```json\n{"contract": "lore", "entry_id": "school-001",'
        ' "second_contract": "none", "second_entry_id": null}\n```'
    )
    assert parsed == Candidate(
        contract="lore",
        entry_id="school-001",
        second_contract="none",
        second_entry_id=None,
    )
    assert parse_candidate('{"contract": "lesson", "entry_id": null}') is None
    assert parse_candidate('{"contract": "lore", "entry_id": null}') is None
    assert parse_candidate("not json") is None


def test_catalogue_is_built_from_the_pack():
    lore = load_lore(FIXTURE)
    system = build_system(lore, "dada")
    for entry in lore.entries:
        assert entry.id in system
    assert "Catalogue" in system


def test_classifier_caches_by_question_previous_and_subject():
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}')
    first = asyncio.run(intent.classify("Where am I?", previous="", subject="dada"))
    second = asyncio.run(intent.classify("Where am I?", previous="", subject="dada"))
    assert first == second
    assert intent.llm.calls == 1
    asyncio.run(intent.classify("Where am I?", previous="and the school?", subject="dada"))
    assert intent.llm.calls == 2


def test_a_failed_reply_is_not_cached():
    intent = ResidualClassifier(
        llm=SequenceLlm(
            [
                "not json",
                '{"contract": "lore", "entry_id": "school-001"}',
            ]
        ),
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
        timeout_s=1.5,
    )
    assert asyncio.run(intent.classify("Where am I?", subject="dada")) is None
    second = asyncio.run(intent.classify("Where am I?", subject="dada"))
    assert second is not None
    assert second.entry_id == "school-001"
    assert intent.llm.calls == 2


def test_classifier_timeout_returns_none():
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}', delay=0.2)
    assert asyncio.run(intent.classify("Where am I?", subject="dada")) is None


def test_classify_sync_is_bounded_and_closes_its_loop():
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}', delay=0.2)
    assert intent.classify_sync("Where am I?", subject="dada") is None
    intent.close()


def test_intent_bedrock_client_has_a_short_timeout_and_no_retries():
    from app.providers.factory import make_llm

    llm = make_llm(
        "bedrock",
        model="apac.amazon.nova-micro-v1:0",
        timeout=1.5,
        max_attempts=0,
    )
    config = llm._client.meta.config
    assert config.read_timeout == 1.5
    # Botocore normalises max_attempts=0 to one total attempt (no retry).
    assert config.retries["total_max_attempts"] == 1


def test_classify_sync_uses_a_persistent_loop():
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}')
    first = intent.classify_sync("Where am I?", subject="dada")
    second = intent.classify_sync("Who's in charge here?", subject="dada")
    assert first is not None and second is not None
    assert intent.calls == 2
    intent.close()


def test_lore_evidence_accepts_the_weak_signal_and_the_margin():
    lore = load_lore(FIXTURE)
    assert _lore_evidence(lore, "Where am I right now?", "dada", "school-001")
    assert _lore_evidence(lore, "What departments are there?", "dada", "school-001")
    assert not _lore_evidence(lore, "What is a Boggart?", "dada", "school-001")
    assert not _lore_evidence(lore, "Where am I right now?", "charms", "crane-001")


def test_router_shadow_records_the_label_and_changes_nothing():
    events: list[dict] = []
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}')
    token = start_trace("shadow", _Sink(events))
    try:
        payload = route(
            route_state("Who's in charge here?"),
            persona=True,
            teaching_terms=lambda _subject: TERMS,
            intent=intent,
            intent_mode="shadow",
            lore=load_lore(FIXTURE),
            personas=PERSONAS,
        )
    finally:
        end_trace(token)
    assert payload["mode"] == "abstain"
    router = next(event for event in events if event["span"] == "router")
    assert router["classifier_label"] == "lore"
    assert router["classifier_entry"] == "school-001"
    assert router["classifier_model"] == "scripted/intent"
    assert router["deterministic_label"] == "abstain"
    assert "classifier_ms" in router


def test_router_on_applies_the_lore_override():
    intent = classifier('{"contract": "lore", "entry_id": "school-001"}')
    payload = route(
        route_state("Who's in charge here?"),
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=intent,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload == {
        "mode": "fact",
        "routed_mode": "fact",
        "fact_ids": ["lore:school-001"],
        "classifier_used": True,
        "classifier_choice": 0,
    }


def test_router_on_canonicalises_an_alias_entry():
    intent = classifier('{"contract": "lore", "entry_id": "academy"}')
    payload = route(
        route_state("Who's in charge here?"),
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=intent,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload == {
        "mode": "fact",
        "routed_mode": "fact",
        "fact_ids": ["lore:school-001"],
        "classifier_used": True,
        "classifier_choice": 0,
    }


def test_router_on_keeps_the_abstain_when_the_evidence_fails():
    intent = classifier('{"contract": "lore", "entry_id": "crane-001"}')
    state = route_state("Who's in charge here?")
    state["subject"] = "charms"
    payload = route(
        state,
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=intent,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload["mode"] == "abstain"


def test_router_on_routes_policy_only_with_a_cue():
    intent = classifier(
        '{"contract": "policy", "entry_id": null, "second_contract": "none"}'
    )
    payload = route(
        route_state("and how is it graded?", previous="What is on the exam?"),
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=intent,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload["mode"] == "policy"

    no_cue = classifier('{"contract": "policy", "entry_id": null}')
    payload = route(
        route_state("Will it be difficult?"),
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=no_cue,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload["mode"] == "abstain"


def test_router_on_routes_persona_when_a_scripted_topic_exists():
    intent = classifier('{"contract": "persona", "entry_id": null}')
    payload = route(
        route_state("what does he teach?", previous="Who is Professor Crane?"),
        persona=True,
        teaching_terms=lambda _subject: TERMS,
        intent=intent,
        intent_mode="on",
        lore=load_lore(FIXTURE),
        personas=PERSONAS,
    )
    assert payload["mode"] == "meta"
    assert payload["meta_topic"] in {"subject", "professor", "boundaries", "identity"}


class _Sink(TraceSink):
    def __init__(self, events: list[dict]) -> None:
        super().__init__(None)
        self.events = events

    def write(self, record: dict) -> None:
        self.events.append(record)
