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
    uncovered_terms,
)
from app.schemas import Chunk, ChunkMetadata


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


class EmptySelector:
    async def select(self, question, **kwargs):
        return []


class StaticRetriever:
    """A fixed corpus result; records whether the fallback was consulted."""

    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.calls = 0

    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        self.calls += 1
        return self.chunks[:top_k]


def _chunk(chunk_id: str, text: str, *, book: int = 3, chapter: int = 7) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=chapter,
            book_name=f"Book {book}",
            chapter_name=f"Chapter {chapter}",
        ),
        score=10.0,
    )


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


class SequencedLlm:
    """Returns one draft per call and records the system prompt."""

    name = "fake/sequenced"

    def __init__(self, drafts: list[str]) -> None:
        self.drafts = list(drafts)
        self.systems: list[str] = []

    async def generate(self, system, prompt, context=None):
        self.systems.append(system)
        return self.drafts.pop(0)

    def stream(self, system, prompt, context=None):
        self.systems.append(system)
        draft = self.drafts.pop(0)

        async def gen():
            yield draft

        return gen()


class CountingEmbedder(KeywordEmbedder):
    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        return await super().embed(texts)


class BadQueryEmbedder:
    name = "fake/bad"

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        if self.calls == 1:
            return [[1.0, 0.0, 0.0] for _ in texts]
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_ask_lesson_retries_an_uncited_draft():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    llm = SequencedLlm(
        [
            "A boggart is a shape-shifter.",
            "A boggart takes your fear's shape "
            "[mat:dada-dark-creatures-boggarts-nature].",
        ]
    )
    resets: list[int] = []

    result = await ask_lesson(
        "How does a boggart work?",
        selector=selector,
        subject="dada",
        llm=llm,
        on_reset=lambda: resets.append(1),
        max_retries=1,
    )

    assert result.attempts == 2
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert resets == [1]


@pytest.mark.asyncio
async def test_ask_lesson_appends_the_persona_suffix():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    llm = SequencedLlm(
        ["A boggart takes your fear's shape [mat:dada-dark-creatures-boggarts-nature]."]
    )

    await ask_lesson(
        "How does a boggart work?",
        selector=selector,
        subject="dada",
        llm=llm,
        persona_suffix="PERSONA-SUFFIX",
    )

    assert "PERSONA-SUFFIX" in llm.systems[0]


@pytest.mark.asyncio
async def test_selector_rejects_a_query_with_the_wrong_dimensions():
    selector = await LessonSelector.build(_store(), BadQueryEmbedder())

    with pytest.raises(ValueError, match="dims"):
        await selector.select("boggart", subject="dada")


@pytest.mark.asyncio
async def test_selector_caches_query_embeddings():
    embedder = CountingEmbedder()
    selector = await LessonSelector.build(_store(), embedder)

    await selector.select("boggart", subject="dada")
    await selector.select("boggart", subject="dada")

    # One call for the material documents at build time, one for the question.
    assert embedder.calls == 2


def test_pack_store_serves_summaries_and_scope():
    store = _store()

    assert store.subjects() == ("dada",)
    assert store.scope() == "dada:fp"
    summary = store.summaries()[0]
    assert summary.subject == "dada"
    assert summary.fingerprint == "fp"
    assert summary.materials == 2
    assert summary.concepts == 2


def test_uncovered_terms_only_flags_terms_the_material_does_not_state():
    materials = _pack().materials

    assert uncovered_terms("How does a boggart work?", materials) == set()
    assert "hippogriff" in uncovered_terms(
        "Compare a boggart with a hippogriff", materials
    )


def test_ground_lesson_answer_keeps_both_citation_spaces():
    chunks = [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]

    result = ground_lesson_answer(
        "A boggart takes your fear's shape "
        "[mat:dada-dark-creatures-boggarts-nature]. "
        "A hippogriff is proud [b3-c07-0099].",
        _pack().materials,
        chunks,
        scope="mixed",
    )

    assert result.scope == "mixed"
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert result.citations == ["b3-c07-0099", "b3-c07-0050"]


def test_ground_lesson_answer_off_pack_rejects_a_material_only_draft():
    chunks = [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]

    result = ground_lesson_answer(
        "A hippogriff is proud [mat:dada-dark-creatures-boggarts-nature].",
        [],
        chunks,
        scope="off_pack",
    )

    assert result.abstained is True
    assert result.abstain_reason == "uncited"


def test_ground_lesson_answer_off_pack_accepts_a_book_citation():
    chunks = [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]

    result = ground_lesson_answer(
        "A hippogriff is proud [b3-c07-0099].",
        [],
        chunks,
        scope="off_pack",
    )

    assert result.abstained is False
    assert result.citations == ["b3-c07-0099"]
    assert result.material_citations == []


@pytest.mark.asyncio
async def test_ask_lesson_falls_back_to_the_corpus_when_the_pack_is_empty():
    retriever = StaticRetriever(
        [_chunk("b1-c01-0000", "A potion is brewed in a cauldron.", book=1, chapter=1)]
    )
    llm = StaticLlm("A potion is brewed in a cauldron [b1-c01-0000].")

    result = await ask_lesson(
        "How do I brew a potion?",
        selector=EmptySelector(),
        subject="dada",
        llm=llm,
        retriever=retriever,
    )

    assert result.abstained is False
    assert result.scope == "off_pack"
    assert result.citations == ["b1-c01-0000"]
    assert result.material_citations == []
    assert "not in the department's notes" in result.answer
    assert retriever.calls == 1


@pytest.mark.asyncio
async def test_ask_lesson_mixed_uses_both_sources():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    retriever = StaticRetriever(
        [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]
    )
    llm = StaticLlm(
        "A boggart takes your fear's shape "
        "[mat:dada-dark-creatures-boggarts-nature]. "
        "A hippogriff is proud [b3-c07-0099]."
    )

    result = await ask_lesson(
        "Compare a boggart with a hippogriff",
        selector=selector,
        subject="dada",
        llm=llm,
        retriever=retriever,
    )

    assert result.abstained is False
    assert result.scope == "mixed"
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert "b3-c07-0099" in result.citations
    assert "set texts" in result.answer.lower()
    assert retriever.calls == 1


@pytest.mark.asyncio
async def test_ask_lesson_mixed_retries_when_only_the_pack_is_cited():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    retriever = StaticRetriever(
        [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]
    )
    llm = SequencedLlm(
        [
            "A boggart takes your fear's shape "
            "[mat:dada-dark-creatures-boggarts-nature].",
            "A boggart takes your fear's shape "
            "[mat:dada-dark-creatures-boggarts-nature]. "
            "A hippogriff is proud [b3-c07-0099].",
        ]
    )
    resets: list[int] = []

    result = await ask_lesson(
        "Compare a boggart with a hippogriff",
        selector=selector,
        subject="dada",
        llm=llm,
        retriever=retriever,
        on_reset=lambda: resets.append(1),
        max_retries=1,
    )

    assert result.attempts == 2
    assert result.scope == "mixed"
    assert result.material_citations == ["dada-dark-creatures-boggarts-nature"]
    assert "b3-c07-0099" in result.citations
    assert resets == [1]


@pytest.mark.asyncio
async def test_ask_lesson_off_pack_abstains_without_a_book_citation():
    retriever = StaticRetriever(
        [_chunk("b1-c01-0000", "A potion is brewed in a cauldron.", book=1, chapter=1)]
    )
    llm = StaticLlm(
        "A potion is brewed in a cauldron "
        "[mat:dada-dark-creatures-boggarts-nature]."
    )

    result = await ask_lesson(
        "How do I brew a potion?",
        selector=EmptySelector(),
        subject="dada",
        llm=llm,
        retriever=retriever,
        max_retries=0,
    )

    assert result.abstained is True
    assert result.abstain_reason == "uncited"
    assert result.scope == "abstained"


@pytest.mark.asyncio
async def test_ask_lesson_fallback_can_be_disabled():
    retriever = StaticRetriever(
        [_chunk("b1-c01-0000", "A potion is brewed in a cauldron.", book=1, chapter=1)]
    )
    llm = StaticLlm("A potion is brewed in a cauldron [b1-c01-0000].")

    result = await ask_lesson(
        "How do I brew a potion?",
        selector=EmptySelector(),
        subject="dada",
        llm=llm,
        retriever=retriever,
        fallback=False,
    )

    assert result.abstained is True
    assert result.abstain_reason == "no_evidence"
    assert result.scope == "abstained"
    assert retriever.calls == 0


@pytest.mark.asyncio
async def test_ask_lesson_in_pack_does_not_call_the_corpus():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())
    retriever = StaticRetriever(
        [_chunk("b3-c07-0099", "A hippogriff is a proud creature.")]
    )
    llm = StaticLlm(
        "A boggart takes your fear's shape "
        "[mat:dada-dark-creatures-boggarts-nature]."
    )

    result = await ask_lesson(
        "How does a boggart work?",
        selector=selector,
        subject="dada",
        llm=llm,
        retriever=retriever,
    )

    assert result.abstained is False
    assert result.scope == "in_pack"
    assert retriever.calls == 0


@pytest.mark.asyncio
async def test_selector_lexical_match_keeps_a_pack_term_in_a_comparison():
    selector = await LessonSelector.build(_store(), KeywordEmbedder())

    selected = selector.select_lexical(
        "Compare a boggart with a hippogriff", subject="dada"
    )

    assert [m.material_id for m in selected] == [
        "dada-dark-creatures-boggarts-nature"
    ]
    assert selector.select_lexical("What is a charm spell?", subject="dada") == []
