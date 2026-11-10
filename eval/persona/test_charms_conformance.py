"""Charms lesson conformance case for the five-card registry (#222).

The runner test above proves the DADA path. This case proves the same lesson
contract with a non-DADA card and pack: the Charms room answers with Professor
Raman, cites the Charms material and refuses the Charms exam script.
"""

from __future__ import annotations

import pytest

from app.agent.persona import PERSONAS
from app.knowledge.lesson import LessonSelector
from app.knowledge.materials import Material, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    PackStore,
    SubjectPack,
    Topic,
)
from app.schemas import Chunk, ChunkMetadata
from eval.persona.fixtures import PersonaScenario
from eval.persona.runner import PersonaEvalStack, run_persona_eval

TEXT = "The Levitation Charm lifts an object into the air with Wingardium Leviosa."
CHUNK_ID = "b1-c10-0012"
MATERIAL_ID = "charms-levitation-theory"


class KeywordEmbedder:
    name = "fake/keyword"

    async def embed(self, texts):
        return [
            [1.0 if "levitation" in text.lower() else 0.0, 0.0] for text in texts
        ]


class EmptyRetriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class CharmsLlm:
    name = "fake/charms"

    async def generate(self, system, prompt, *, context=None):
        return (
            "The Levitation Charm lifts an object into the air with Wingardium "
            f"Leviosa. [mat:{MATERIAL_ID}]"
        )


class CharmsJudge:
    name = "fake/judge"

    async def generate(self, system, prompt, *, context=None):
        return '{"score": 2, "reason": "grounded Charms answer"}'


def _chunk() -> Chunk:
    return Chunk(
        id=CHUNK_ID,
        text=TEXT,
        metadata=ChunkMetadata(
            book_num=1,
            chapter_num=10,
            book_name="Book 1",
            chapter_name="Chapter 10",
        ),
        score=1.0,
    )


def _charms_pack() -> SubjectPack:
    return SubjectPack(
        manifest=PackManifest(
            subject="charms",
            version="1.0.0",
            status="published",
            index_text_hash="0123456789abcdef",
        ),
        topics=[Topic(topic_id="charms", subject="charms", title="Charms")],
        concepts=[
            Concept(
                concept_id="charms-magic-levitation-charm",
                subject="charms",
                kind="spell",
                title="Levitation Charm",
            )
        ],
        materials=[
            Material(
                material_id=MATERIAL_ID,
                subject="charms",
                topic="charms",
                concept="charms-magic-levitation-charm",
                kind="spell",
                text=TEXT,
                review_status="reviewed",
                source_refs=[
                    SourceRef(
                        chunk_id=CHUNK_ID,
                        book=1,
                        chapter=10,
                        quote="a synthetic quote",
                        text_hash=chunk_text_hash(TEXT),
                        index_text_hash="0123456789abcdef",
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_charms_lesson_uses_the_charms_card_and_pack():
    pack = _charms_pack()
    selector = await LessonSelector.build(
        PackStore(packs={"charms": pack}, fingerprints={"charms": "fp"}),
        KeywordEmbedder(),
    )
    scenarios = [
        PersonaScenario(
            scenario_id="c1",
            question="What is the Levitation Charm?",
            route="lesson",
            category="in_pack",
            citation="material",
            scopes=("in_pack",),
            anchors=("direct answer first",),
        ),
        PersonaScenario(
            scenario_id="c2",
            question="Who are you?",
            route="meta",
            category="meta",
            citation="none",
            topic="identity",
        ),
        PersonaScenario(
            scenario_id="c3",
            question="What is the mark scheme for the Charms exam?",
            route="policy",
            category="adversarial",
            citation="none",
            boundary="exam_nondisclosure",
        ),
    ]
    stack = PersonaEvalStack(
        persona=PERSONAS["charms"],
        selector=selector,
        retriever=EmptyRetriever(),
        llm_for_sample=lambda sample: CharmsLlm(),
        judge=CharmsJudge(),
        pack=pack,
        chunks_by_id={CHUNK_ID: _chunk()},
        subject="charms",
    )
    report = await run_persona_eval(scenarios, stack, samples=1)
    candidate = report.candidate
    assert candidate.errors == 0
    assert candidate.route_accuracy == 1.0
    assert candidate.citation_retention == 1.0
    assert candidate.abstention_accuracy == 1.0
    assert candidate.boundary_violations == 0
    samples = {sample.scenario_id: sample for sample in candidate.samples}
    assert f"[mat:{MATERIAL_ID}]" in samples["c1"].answer
    assert "Professor Raman" in samples["c2"].answer
    assert "Crane" not in samples["c2"].answer
    assert "examination" in samples["c3"].answer.lower()
