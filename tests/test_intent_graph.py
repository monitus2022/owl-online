"""The residual override end to end through the compiled graph (#327)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.agent.graph import build_graph
from app.agent.intent import ResidualClassifier
from app.agent.persona import PERSONAS
from app.knowledge.lore import load_lore
from app.providers.fakes import FakeLlm, FakeRetriever

FIXTURE = Path(__file__).parents[1] / "eval" / "fixtures" / "lore"


class StubClassifierLlm:
    name = "stub/intent"

    async def generate(self, system, prompt, context=None):
        return (
            '{"contract": "lore", "entry_id": "school-001",'
            ' "second_contract": "none", "second_entry_id": null}'
        )

    def stream(self, system, prompt, context=None):  # pragma: no cover - contract
        raise NotImplementedError


class DummyLesson:
    """A selector shape that supplies the teaching gate but never runs."""

    def concept_terms(self, subject):
        return set()

    def subjects(self):
        return {"dada"}

    async def select(self, *args, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("the lesson selector must not run on a fact turn")


def test_graph_applies_the_evidence_gated_fact_override():
    lore = load_lore(FIXTURE)
    intent = ResidualClassifier(
        llm=StubClassifierLlm(), lore=lore, personas=PERSONAS, timeout_s=1.0
    )
    graph = build_graph(
        FakeRetriever(),
        FakeLlm(),
        lore=lore,
        personas=PERSONAS,
        intent_classifier=intent,
        intent_mode="on",
        lesson=DummyLesson(),
        lesson_subject="dada",
        default_subject="dada",
    )
    state = {
        "question": "Who's in charge here?",
        "subject": "dada",
        "requested_mode": "lesson",
        "persona_enabled": True,
    }
    result = asyncio.run(graph.ainvoke(state))
    assert result["mode"] == "fact"
    assert result["typed_citations"] == ["lore:school-001"]
    assert "Cotswolds" in result["answer"]
