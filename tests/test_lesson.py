"""Lesson-mode tests: derived selector, material grounding, abstention.

All fixtures are synthetic; no corpus text. The selector is checked with a
keyword embedder so the ranking is deterministic and offline.
"""

import pytest

from app.knowledge.lesson import LessonSelector
from app.knowledge.materials import Material, SourceRef
from app.knowledge.packs import (
    Concept,
    PackManifest,
    PackStore,
    SubjectPack,
    Topic,
)
from app.pipeline.generate.lesson import (
    ask_lesson,
    ground_lesson_answer,
)


class KeywordEmbedder:
    """Three dimensions, one per concept; deterministic and offline."""

    name = "fake/keyword"

    async def embed(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "boggart" in lowered else 0.0,
                    1.0 if "patronus" in lowered else 0.0,
                    1.0 if "fidelius" in lowered else 0.0,
                ]
            )
        return vectors


class StaticLlm:
    """Returns one fixed draft; streaming yields it in one piece."""

    name = "fake/llm"

    def __init__(self, draft: str) -> None:
        self.draft = draft

    async def generate(self, system, prompt, context=None):
        return self.draft

    def stream(self, system, prompt, context=None):
        async def gen():
            yield self.draft

        return gen()


def _ref(chunk_id: str) -> SourceRef:
    return SourceRef(
        chunk_id=chunk_id,
        book=3,
        chapter=7,
        quote="a synthetic quote",
        text_hash="0123456789abcdef",
        index_text_hash="fedcba9876543210",
    )


def _pack() -> SubjectPack:
    concepts = [
        Concept(
            concept_id="dada-creature-boggart",
            subject="dada",
            kind="creature",
            title="Boggart",
            aliases=("boggart", "boggart banishing"),
        ),
        Concept(
            concept_id="dada-magic-patronus",
            subject="dada",
            kind="spell",
            title="Patronus",
            aliases=("patronus",),
        ),
    ]
    materials = [
        Material(
            material_id="dada-dark-creatures-boggarts-nature",
            subject="dada",
            topic="dark-creatures",
            concept="dada-creature-boggart",
            kind="creature",
            text="A boggart takes the shape of what the watcher fears most.",
            review_status="reviewed",
            source_refs=[_ref("b3-c07-0050")],
        ),
        Material(
            material_id="dada-magic-patronus-theory",
            subject="dada",
            topic="defensive-magic",
            concept="dada-magic-patronus",
            kind="spell",
            text="A patronus is a silver guardian summoned by a happy memory.",
            review_status="reviewed",
            source_refs=[_ref("b3-c12-0010")],
        ),
    ]
    return SubjectPack(
        manifest=PackManifest(
            subject="dada",
            version="1.0.0",
            status="published",
            index_text_hash="fedcba9876543210",
        ),
        topics=[
            Topic(topic_id="dark-creatures", subject="dada", title="Dark creatures"),
            Topic(topic_id="defensive-magic", subject="dada", title="Defensive magic"),
        ],
        concepts=concepts,
        materials=materials,
    )


def _store() -> PackStore:
    return PackStore(packs={"dada": _pack()}, fingerprints={"dada": "fp"})


@pytest.mark.asyncio
async def test_selector_prefers_the_matching_material():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())

    selected = await selector.select(
        "What does a boggart look like?", subject="dada", top_k=1
    )

    assert [m.material_id for m in selected] == ["dada-dark-creatures-boggarts-nature"]


@pytest.mark.asyncio
async def test_selector_is_subject_scoped_and_unknown_subject_is_empty():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())

    assert await selector.select("boggart", subject="charms") == []
    assert selector.subjects() == ("dada",)


@pytest.mark.asyncio
async def test_selector_abstains_below_the_score_floor():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())

    selected = await selector.select(
        "What is the capital of Iceland?", subject="dada", min_score=0.58
    )

    assert selected == []


@pytest.mark.asyncio
async def test_selector_top_k_returns_multiple_materials():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())

    selected = await selector.select(
        "Compare a boggart with a patronus", subject="dada", top_k=2
    )

    assert len(selected) == 2


def test_ground_lesson_answer_resolves_source_refs():
    materials = _pack().materials

    result = ground_lesson_answer(
        "It takes your fear's shape [mat:dada-dark-creatures-boggarts-nature].",
        materials,
    )

    assert result.abstained is False
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert result.citations == ["b3-c07-0050"]


def test_ground_lesson_answer_strips_unknown_material_ids():
    materials = _pack().materials

    result = ground_lesson_answer(
        "A claim [mat:not-a-material; dada-magic-patronus-theory].",
        materials,
    )

    assert result.material_citations == ["dada-magic-patronus-theory"]
    assert "not-a-material" not in result.answer


def test_ground_lesson_answer_abstains_without_a_citation():
    result = ground_lesson_answer("It is a shape-shifter.", _pack().materials)

    assert result.abstained is True
    assert result.abstain_reason == "uncited"


@pytest.mark.asyncio
async def test_ask_lesson_returns_grounded_material_citations():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    llm = StaticLlm(
        "A boggart takes the shape of your fear [mat:dada-dark-creatures-boggarts-nature]."
    )

    result = await ask_lesson(
        "How does a boggart work?", selector=selector, subject="dada", llm=llm
    )

    assert result.abstained is False
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert result.citations == ["b3-c07-0050"]
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_ask_lesson_abstains_when_the_draft_cites_nothing():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    llm = StaticLlm("A boggart is a shape-shifter.")

    result = await ask_lesson(
        "How does a boggart work?",
        selector=selector,
        subject="dada",
        llm=llm,
        max_retries=0,
    )

    assert result.abstained is True
    assert result.abstain_reason == "uncited"
    assert result.material_citations == []


@pytest.mark.asyncio
async def test_ask_lesson_abstains_when_the_selector_returns_nothing():
    class EmptySelector:
        async def select(self, question, **kwargs):
            return []

    llm = StaticLlm("Anything [mat:dada-dark-creatures-boggarts-nature].")

    result = await ask_lesson(
        "How do I brew a potion?", selector=EmptySelector(), subject="dada", llm=llm
    )

    assert result.abstained is True
    assert result.abstain_reason == "no_evidence"
    assert result.attempts == 0
