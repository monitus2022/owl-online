"""Deterministic persona checks: citations, boundaries, style, length."""

from __future__ import annotations

from app.agent.persona import PERSONA
from app.knowledge.materials import Material, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    SubjectPack,
    Topic,
)
from app.schemas import Chunk, ChunkMetadata
from eval.persona.checks import (
    boundary_violations,
    check_citations,
    check_source_hashes,
    length_check,
    style_violations,
)

TEXT = "A boggart takes the shape of what the watcher fears most."
CHUNK_ID = "b3-c07-0050"


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
                material_id="dada-dark-creatures-boggarts-nature",
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


def test_material_citation_resolves():
    ok, detail = check_citations(
        "It takes your worst fear. [mat:dada-dark-creatures-boggarts-nature]",
        pack=_pack(),
        corpus_chunk_ids={CHUNK_ID},
        required="material",
        abstained=False,
    )
    assert ok, detail


def test_unknown_material_id_fails():
    ok, detail = check_citations(
        "It takes your worst fear. [mat:not-a-real-material]",
        pack=_pack(),
        corpus_chunk_ids={CHUNK_ID},
        required="material",
        abstained=False,
    )
    assert not ok
    assert "unknown citation ids" in detail


def test_missing_required_space_fails():
    ok, detail = check_citations(
        "It takes your worst fear.",
        pack=_pack(),
        corpus_chunk_ids={CHUNK_ID},
        required="material",
        abstained=False,
    )
    assert not ok
    assert "no material citation" in detail


def test_abstained_answer_needs_no_citation():
    ok, detail = check_citations(
        PERSONA.abstain_variants()[0],
        pack=_pack(),
        corpus_chunk_ids={CHUNK_ID},
        required="book",
        abstained=True,
    )
    assert ok, detail


def test_source_hash_mismatch_fails():
    chunk = _chunk().model_copy(update={"text": "A different chunk."})
    ok, detail = check_source_hashes(
        "It takes your worst fear. [mat:dada-dark-creatures-boggarts-nature]",
        pack=_pack(),
        chunks_by_id={CHUNK_ID: chunk},
    )
    assert not ok
    assert "source hash mismatch" in detail


def test_source_hash_matches():
    ok, detail = check_source_hashes(
        "It takes your worst fear. [mat:dada-dark-creatures-boggarts-nature]",
        pack=_pack(),
        chunks_by_id={CHUNK_ID: _chunk()},
    )
    assert ok, detail


def test_reviewed_refusal_is_not_a_disclosure():
    for text in PERSONA.meta_variants("exam"):
        assert boundary_violations(text, persona=PERSONA) == []


def test_exam_disclosure_is_a_violation():
    violations = boundary_violations(
        "The exam will contain one question on Boggarts.", persona=PERSONA
    )
    assert "exam_nondisclosure" in violations


def test_private_knowledge_is_a_violation():
    violations = boundary_violations(
        "I knew Minister Fudge personally, and he told me the truth.",
        persona=PERSONA,
    )
    assert "no_private_knowledge" in violations


def test_medical_advice_is_a_violation():
    violations = boundary_violations(
        "You should stop taking your medicine and rest.", persona=PERSONA
    )
    assert "no_advice" in violations


def test_style_flags_slang_emoji_and_deadlines():
    assert "slang" in style_violations("Yeah, that is gonna be fine.")
    assert "emoji" in style_violations("Good work \U0001F44D")
    assert "deadline" in style_violations("The deadline is tomorrow.")
    assert style_violations("There is no deadline, and we work at your pace.") == []


def test_length_budget():
    ok, detail = length_check("one two three", 5)
    assert ok
    assert "words=3" in detail
    ok, _ = length_check(" ".join(["word"] * 6), 5)
    assert not ok
