"""End-to-end runner test with a tiny pack, fake generator and fake judge."""

from __future__ import annotations

import pytest

from app.agent.persona import PERSONA
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

TEXT = "A boggart takes the shape of what the watcher fears most."
CHUNK_ID = "b3-c07-0050"
MATERIAL_ID = "dada-dark-creatures-boggarts-nature"


class KeywordEmbedder:
    name = "fake/keyword"

    async def embed(self, texts):
        return [
            [1.0 if "boggart" in text.lower() else 0.0, 0.0] for text in texts
        ]


class EmptyRetriever:
    async def retrieve(self, query: str, top_k: int):
        return []


class VoiceLlm:
    name = "fake/voice"

    async def generate(self, system, prompt, *, context=None):
        if "You are teaching a student directly" in system:
            return (
                "A Boggart is a shape-shifter that takes the form of what you "
                "fear most. It matters because fear is what feeds it. For "
                "example, the notes describe it becoming a spider. Be careful "
                "to keep a clear comic image. What shape would you choose? "
                f"[mat:{MATERIAL_ID}]"
            )
        return (
            "A Boggart is a shape-shifter that takes the form of what the "
            f"watcher fears most. [mat:{MATERIAL_ID}]"
        )


class VoiceJudge:
    name = "fake/judge"

    async def generate(self, system, prompt, *, context=None):
        if "What shape would you choose?" in prompt:
            return '{"score": 2, "reason": "full teaching shape"}'
        return '{"score": 1, "reason": "flat summary"}'


def _chunk() -> Chunk:
    return Chunk(
        id=CHUNK_ID,
        text=TEXT,
        metadata=ChunkMetadata(
            book_num=3,
            chapter_num=7,
            book_name="Book 3",
            chapter_name="Chapter 7",
        ),
        score=1.0,
    )


def _pack() -> SubjectPack:
    return SubjectPack(
        manifest=PackManifest(
            subject="dada",
            version="1.0.0",
            status="published",
            index_text_hash="fedcba9876543210",
        ),
        topics=[Topic(topic_id="dark-creatures", subject="dada", title="Dark creatures")],
        concepts=[
            Concept(
                concept_id="dada-creature-boggart",
                subject="dada",
                kind="creature",
                title="Boggart",
            )
        ],
        materials=[
            Material(
                material_id=MATERIAL_ID,
                subject="dada",
                topic="dark-creatures",
                concept="dada-creature-boggart",
                kind="creature",
                text=TEXT,
                review_status="reviewed",
                source_refs=[
                    SourceRef(
                        chunk_id=CHUNK_ID,
                        book=3,
                        chapter=7,
                        quote="a synthetic quote",
                        text_hash=chunk_text_hash(TEXT),
                        index_text_hash="fedcba9876543210",
                    )
                ],
            )
        ],
    )


@pytest.mark.asyncio
async def test_candidate_improves_voice_without_losing_citations():
    pack = _pack()
    selector = await LessonSelector.build(
        PackStore(packs={"dada": pack}, fingerprints={"dada": "fp"}),
        KeywordEmbedder(),
    )
    scenarios = [
        PersonaScenario(
            scenario_id="s1",
            question="What is a boggart?",
            route="lesson",
            category="in_pack",
            citation="material",
            scopes=("in_pack",),
            anchors=("direct answer first",),
        ),
        PersonaScenario(
            scenario_id="s2",
            question="Who are you?",
            route="meta",
            category="meta",
            citation="none",
            topic="identity",
        ),
        PersonaScenario(
            scenario_id="s3",
            question="What is the capital of France?",
            route="lesson",
            category="off_topic",
            citation="book",
            scopes=("off_pack", "abstained"),
        ),
    ]
    stack = PersonaEvalStack(
        persona=PERSONA,
        selector=selector,
        retriever=EmptyRetriever(),
        llm_for_sample=lambda sample: VoiceLlm(),
        judge=VoiceJudge(),
        pack=pack,
        chunks_by_id={CHUNK_ID: _chunk()},
    )
    report = await run_persona_eval(scenarios, stack, samples=3)
    assert report.baseline.persona_pass_rate == 0.0
    assert report.candidate.persona_pass_rate == 1.0
    assert report.candidate.citation_retention == 1.0
    assert report.candidate.abstention_accuracy == 1.0
    assert report.candidate.boundary_violations == 0
    assert report.candidate.style_violations == 0
    assert report.ok, report.gate_reasons()
