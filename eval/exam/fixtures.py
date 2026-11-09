"""Invented bank fixtures for the eval tests; no corpus prose."""

from __future__ import annotations

from app.exam.bank import (
    BankItem,
    BankManifest,
    EvidenceSnapshot,
    ExamBank,
    McqOption,
    RubricCriterion,
)
from app.knowledge.materials import Material, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    SubjectPack,
    Topic,
    pack_fingerprint,
)
from app.schemas import Chunk, ChunkMetadata

INDEX_HASH = "test-index"
TEXT = (
    "The sample Riddikulus lesson turns a feared shape into a comic one. "
    "The caster holds a funny image while speaking the word."
)


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            book_num=3,
            chapter_num=7,
            book_name="Prisoner of Azkaban",
            chapter_name="The Boggart in the Wardrobe",
        ),
    )


def _ref(chunk: Chunk, quote: str) -> SourceRef:
    return SourceRef(
        chunk_id=chunk.id,
        book=chunk.metadata.book_num,
        chapter=chunk.metadata.chapter_num,
        quote=quote,
        text_hash=chunk_text_hash(chunk.text),
        index_text_hash=INDEX_HASH,
    )


def _snapshot(ref: SourceRef) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        chunk_id=ref.chunk_id,
        book=ref.book,
        chapter=ref.chapter,
        quote=ref.quote,
        text_hash=ref.text_hash,
        index_text_hash=ref.index_text_hash,
    )


def _mcq(ref: SourceRef) -> BankItem:
    options = (
        McqOption(option_id="a", text="Riddikulus"),
        McqOption(option_id="b", text="Expecto Patronum"),
        McqOption(option_id="c", text="Protego"),
        McqOption(option_id="d", text="Stupefy"),
        McqOption(option_id="e", text="Expelliarmus"),
        McqOption(option_id="f", text="Lumos"),
    )
    return BankItem(
        item_id="dada-mcq-001",
        subject="dada",
        kind="mcq",
        prompt="Which charm turns the sample feared shape into a comic one?",
        topic="dark-creatures",
        concepts=("dada-creature-boggart",),
        material_id="dada-test-boggart",
        source_refs=(ref,),
        evidence_snapshot=_snapshot(ref),
        difficulty="recall",
        marks=3,
        options=options,
        correct_option_id="a",
        rationale="The sample counter is Riddikulus.",
        review_status="reviewed",
        prompt_version="dada-bank-v1",
    )


def _short(ref: SourceRef) -> BankItem:
    return BankItem(
        item_id="dada-short-001",
        subject="dada",
        kind="short_answer",
        prompt="Explain the sample Riddikulus lesson.",
        topic="dark-creatures",
        concepts=("dada-creature-boggart",),
        material_id="dada-test-boggart",
        source_refs=(ref,),
        evidence_snapshot=_snapshot(ref),
        difficulty="explanation",
        marks=8,
        rubric=(
            RubricCriterion(
                criterion_id="correctness",
                description="States the comic transformation.",
                max_marks=4,
            ),
            RubricCriterion(
                criterion_id="completeness",
                description="Explains the caster's funny image.",
                max_marks=4,
            ),
        ),
        required_points=("comic", "feared shape"),
        model_answer=(
            "The sample Riddikulus lesson turns a feared shape into a comic one. "
            "The caster holds a funny image while speaking the word. "
            "The word alone is not enough."
        ),
        rationale="The sample rubric separates correctness from completeness.",
        review_status="reviewed",
        prompt_version="dada-bank-v1",
    )


def build_bank() -> tuple[ExamBank, SubjectPack, dict[str, Chunk], str]:
    """A valid one-MCQ and one-short bank with a one-material pack."""
    chunk = _chunk("b3-c07-0001", TEXT)
    ref = _ref(chunk, TEXT[:40])
    pack = SubjectPack(
        manifest=PackManifest(
            subject="dada", version="1.0.0", status="published", tier="owl"
        ),
        topics=[
            Topic(topic_id="dark-creatures", subject="dada", title="Dark Creatures")
        ],
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
                material_id="dada-test-boggart",
                subject="dada",
                topic="dark-creatures",
                concept="dada-creature-boggart",
                kind="creature",
                text=TEXT,
                review_status="reviewed",
                source_refs=[ref],
            )
        ],
    )
    manifest = BankManifest(
        subject="dada",
        tier="owl",
        version="1.0.0",
        status="published",
        built_at="2026-11-09T00:00:00Z",
        reviewed_at="2026-11-09T00:00:00Z",
        pack_version="1.0.0",
        pack_fingerprint=pack_fingerprint(pack),
        index_text_hash=INDEX_HASH,
        generator_model="deepseek/deepseek-v4.1-flash",
        generator_temperature=0.0,
        generator_prompt_version="test-gen",
        judge_model="mistralai/mistral-small-3.2-24b-instruct",
        judge_temperature=0.0,
        judge_prompt_version="dada-bank-judge-v2",
        mcq_count=1,
        short_answer_count=1,
    )
    bank = ExamBank(manifest=manifest, items=[_mcq(ref), _short(ref)])
    return bank, pack, {chunk.id: chunk}, INDEX_HASH


__all__ = ["INDEX_HASH", "TEXT", "build_bank"]
