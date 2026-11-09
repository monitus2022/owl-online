"""Tests for the exam-bank schema, validator and SQLite store (#189)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.exam.bank import (
    BankItem,
    BankManifest,
    EvidenceSnapshot,
    ExamBank,
    McqOption,
    RubricCriterion,
    load_exam_bank,
    structure_record,
    validate_bank,
    write_exam_bank,
)
from app.knowledge.materials import Material, SourceRef, chunk_text_hash
from app.knowledge.packs import Concept, PackManifest, SubjectPack, Topic, pack_fingerprint
from app.schemas import Chunk, ChunkMetadata
from app.storage.exam_store import ExamStore

INDEX_HASH = "test-index"
TEXT_ONE = (
    "The sample Riddikulus lesson turns a feared shape into a comic one. "
    "The caster holds a funny image while speaking the word."
)
TEXT_TWO = (
    "The sample boggart changes shape for each observer. "
    "Its alone-form is unknown to the record."
)


def _chunk(chunk_id: str, text: str, chapter: int) -> Chunk:
    return Chunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            book_num=3,
            chapter_num=chapter,
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


def _pack() -> tuple[SubjectPack, dict[str, Chunk]]:
    chunk_one = _chunk("b3-c07-0001", TEXT_ONE, 7)
    chunk_two = _chunk("b3-c07-0002", TEXT_TWO, 7)
    ref_one = _ref(chunk_one, TEXT_ONE[:40])
    ref_two = _ref(chunk_two, TEXT_TWO[:40])
    pack = SubjectPack(
        manifest=PackManifest(subject="dada", version="1.0.0", status="published"),
        topics=[
            Topic(topic_id="dark-creatures", subject="dada", title="Dark Creatures"),
            Topic(topic_id="defensive-magic", subject="dada", title="Defensive Magic"),
        ],
        concepts=[
            Concept(
                concept_id="dada-magic-boggart-banishing-spell",
                subject="dada",
                kind="spell",
                title="Boggart Banishing Spell",
            ),
            Concept(
                concept_id="dada-creature-boggart",
                subject="dada",
                kind="creature",
                title="Boggart",
            ),
        ],
        materials=[
            Material(
                material_id="dada-test-riddikulus",
                subject="dada",
                topic="dark-creatures",
                concept="dada-magic-boggart-banishing-spell",
                kind="spell",
                text=TEXT_ONE,
                review_status="reviewed",
                source_refs=[ref_one],
            ),
            Material(
                material_id="dada-test-boggart",
                subject="dada",
                topic="dark-creatures",
                concept="dada-creature-boggart",
                kind="creature",
                text=TEXT_TWO,
                review_status="reviewed",
                source_refs=[ref_two],
            ),
        ],
    )
    return pack, {chunk_one.id: chunk_one, chunk_two.id: chunk_two}


def _mcq(ref: SourceRef, *, item_id: str = "dada-mcq-001") -> BankItem:
    options = (
        McqOption(option_id="a", text="Riddikulus"),
        McqOption(option_id="b", text="Expecto Patronum"),
        McqOption(option_id="c", text="Protego"),
        McqOption(option_id="d", text="Stupefy"),
        McqOption(option_id="e", text="Expelliarmus"),
        McqOption(option_id="f", text="Lumos"),
    )
    return BankItem(
        item_id=item_id,
        subject="dada",
        kind="mcq",
        prompt="Which charm turns a boggart's shape aside?",
        topic="dark-creatures",
        concepts=("dada-magic-boggart-banishing-spell",),
        material_id="dada-test-riddikulus",
        source_refs=(ref,),
        evidence_snapshot=_snapshot(ref),
        difficulty="recall",
        marks=3,
        options=options,
        correct_option_id="a",
        rationale="Riddikulus is the boggart counter.",
        review_status="reviewed",
        prompt_version="test-v1",
    )


def _mcq_two(ref: SourceRef) -> BankItem:
    options = (
        McqOption(option_id="a", text="Nobody knows what it looks like alone"),
        McqOption(option_id="b", text="It always looks like a black dog"),
        McqOption(option_id="c", text="It looks like its caster"),
        McqOption(option_id="d", text="It has no true form"),
        McqOption(option_id="e", text="It looks like a dementor"),
        McqOption(option_id="f", text="It looks like the last person who saw it"),
    )
    return BankItem(
        item_id="dada-mcq-002",
        subject="dada",
        kind="mcq",
        prompt="What is known about a boggart's form when it is alone?",
        topic="dark-creatures",
        concepts=("dada-creature-boggart",),
        material_id="dada-test-boggart",
        source_refs=(ref,),
        evidence_snapshot=_snapshot(ref),
        difficulty="recall",
        marks=3,
        options=options,
        correct_option_id="a",
        rationale="The material says nobody knows its solitary form.",
        review_status="reviewed",
        prompt_version="test-v1",
    )


def _short(ref: SourceRef, *, item_id: str = "dada-short-001") -> BankItem:
    return BankItem(
        item_id=item_id,
        subject="dada",
        kind="short_answer",
        prompt="Explain the Riddikulus charm and the mental component required.",
        topic="dark-creatures",
        concepts=("dada-magic-boggart-banishing-spell",),
        material_id="dada-test-riddikulus",
        source_refs=(ref,),
        evidence_snapshot=_snapshot(ref),
        difficulty="explanation",
        marks=8,
        rubric=(
            RubricCriterion(
                criterion_id="correctness",
                description="States the humorous transformation.",
                max_marks=4,
            ),
            RubricCriterion(
                criterion_id="completeness",
                description="Explains the mental image and the retreat.",
                max_marks=4,
            ),
        ),
        required_points=("comic image", "feared shape"),
        model_answer=(
            "The Riddikulus charm forces a boggart into a humorous form. "
            "The caster must hold a clear comic image while performing the charm. "
            "Laughter weakens the creature and forces it to retreat."
        ),
        review_status="reviewed",
        prompt_version="test-v1",
    )


def _bank() -> tuple[ExamBank, SubjectPack, dict[str, Chunk]]:
    pack, chunks = _pack()
    ref_one = _ref(chunks["b3-c07-0001"], TEXT_ONE[:40])
    ref_two = _ref(chunks["b3-c07-0002"], TEXT_TWO[:40])
    manifest = BankManifest(
        subject="dada",
        tier="owl",
        version="1.0.0",
        status="published",
        built_at="2026-11-09T00:00:00Z",
        pack_version="1.0.0",
        pack_fingerprint=pack_fingerprint(pack),
        index_text_hash=INDEX_HASH,
        generator_model="test-generator",
        generator_prompt_version="gen-v1",
        judge_model="test-judge",
        judge_prompt_version="judge-v1",
        mcq_count=2,
        short_answer_count=2,
    )
    items = [
        _mcq(ref_one),
        _mcq_two(ref_two),
        _short(ref_one),
        BankItem(
            item_id="dada-short-002",
            subject="dada",
            kind="short_answer",
            prompt="Explain what a boggart's form reveals about the caster.",
            topic="dark-creatures",
            concepts=("dada-creature-boggart",),
            material_id="dada-test-boggart",
            source_refs=(ref_two,),
            evidence_snapshot=_snapshot(ref_two),
            difficulty="explanation",
            marks=8,
            rubric=(
                RubricCriterion(
                    criterion_id="correctness",
                    description="States that the form is the caster's fear.",
                    max_marks=4,
                ),
                RubricCriterion(
                    criterion_id="completeness",
                    description="Explains the moment the form is chosen.",
                    max_marks=4,
                ),
            ),
            required_points=("each observer", "alone-form"),
            model_answer=(
                "The sample creature changes shape for each observer who meets it. "
                "The record never states what it looks like when no one is present. "
                "Its form is fixed only at the moment of the encounter."
            ),
            review_status="reviewed",
            prompt_version="test-v1",
        ),
    ]
    return ExamBank(manifest=manifest, items=items), pack, chunks


def test_valid_bank_roundtrip_and_store(tmp_path: Path) -> None:
    bank, pack, chunks = _bank()
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert validation.ok
    assert validation.coverage.total == 4
    assert validation.coverage.by_kind == {"mcq": 2, "short_answer": 2}

    bank.manifest = bank.manifest.model_copy(
        update={"mcq_count": 0, "short_answer_count": 0}
    )
    directory = tmp_path / "dada"
    write_exam_bank(bank, directory)
    loaded = load_exam_bank(directory)
    assert loaded.counts() == {"mcq": 2, "short_answer": 2}
    assert loaded.manifest.mcq_count == 2

    with ExamStore(tmp_path / "exams.db") as store:
        store.replace_bank(loaded)
        store.replace_bank(loaded, force=True)
        assert store.counts("dada", "1.0.0") == {"mcq": 2, "short_answer": 2}
        assert store.items("dada", "1.0.0") == sorted(loaded.items, key=lambda item: item.item_id)
        assert store.item("dada-mcq-001") is not None
        assert store.manifest("dada", "1.0.0") == loaded.manifest


def _row(item: BankItem) -> dict:
    return item.model_dump(mode="json")


def _first_mcq() -> BankItem:
    _, chunks = _pack()
    return _mcq(_ref(chunks["b3-c07-0001"], TEXT_ONE[:40]))


def _first_short() -> BankItem:
    _, chunks = _pack()
    return _short(_ref(chunks["b3-c07-0001"], TEXT_ONE[:40]))


def test_mcq_requires_six_options() -> None:
    row = _row(_first_mcq())
    row["options"] = row["options"][:5]
    with pytest.raises(ValidationError, match="at least six options"):
        BankItem.model_validate(row)


def test_mcq_requires_one_correct_option() -> None:
    row = _row(_first_mcq())
    row["correct_option_id"] = "z"
    with pytest.raises(ValidationError, match="correct_option_id"):
        BankItem.model_validate(row)


def test_mcq_rejects_trivial_options() -> None:
    row = _row(_first_mcq())
    row["options"][0]["text"] = "All of the above"
    with pytest.raises(ValidationError, match="all-of-the-above"):
        BankItem.model_validate(row)


def test_mcq_rejects_duplicate_option_text() -> None:
    row = _row(_first_mcq())
    row["options"][1]["text"] = row["options"][0]["text"]
    with pytest.raises(ValidationError, match="option texts must be unique"):
        BankItem.model_validate(row)


def test_short_answer_requires_two_to_three_sentences() -> None:
    row = _row(_first_short())
    row["model_answer"] = "Too short."
    with pytest.raises(ValidationError, match="2-3 sentences"):
        BankItem.model_validate(row)


def test_short_answer_rubric_must_sum_to_marks() -> None:
    row = _row(_first_short())
    row["rubric"][1]["max_marks"] = 3
    with pytest.raises(ValidationError, match="sum to the item marks"):
        BankItem.model_validate(row)


def test_short_answer_requires_correctness_and_completeness() -> None:
    row = _row(_first_short())
    row["rubric"][0]["criterion_id"] = "clarity"
    with pytest.raises(ValidationError, match="correctness and completeness"):
        BankItem.model_validate(row)


def test_short_answer_requires_required_points() -> None:
    row = _row(_first_short())
    row["required_points"] = []
    with pytest.raises(ValidationError, match="2-3 required points"):
        BankItem.model_validate(row)


def test_short_answer_requires_a_rubric() -> None:
    row = _row(_first_short())
    row["rubric"] = []
    with pytest.raises(ValidationError, match="at least two rubric criteria"):
        BankItem.model_validate(row)


def test_evidence_snapshot_must_match_source_ref() -> None:
    row = _row(_first_mcq())
    row["evidence_snapshot"]["chunk_id"] = "b3-c07-0002"
    with pytest.raises(ValidationError, match="evidence_snapshot must match"):
        BankItem.model_validate(row)


def test_validate_bank_reports_answer_positions() -> None:
    bank, pack, chunks = _bank()
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert validation.ok
    assert validation.coverage.answer_positions["0"] == 2


def test_validate_bank_rejects_unknown_topic() -> None:
    bank, pack, chunks = _bank()
    bank.items[0] = bank.items[0].model_copy(update={"topic": "missing"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("unknown topic" in error for error in validation.errors)


def test_validate_bank_rejects_count_mismatch() -> None:
    bank, pack, chunks = _bank()
    bank.manifest = bank.manifest.model_copy(update={"mcq_count": 1})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("mcq_count" in error for error in validation.errors)


def test_validate_bank_rejects_draft_pack() -> None:
    bank, pack, chunks = _bank()
    pack.manifest = pack.manifest.model_copy(update={"status": "draft"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("source pack is not published" in error for error in validation.errors)


def test_validate_bank_rejects_unreviewed_material() -> None:
    bank, pack, chunks = _bank()
    pack.materials[0] = pack.materials[0].model_copy(update={"review_status": "draft"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("cited material is not reviewed" in error for error in validation.errors)


def test_validate_bank_rejects_unsupported_required_point() -> None:
    bank, pack, chunks = _bank()
    short = next(item for item in bank.items if item.kind == "short_answer")
    index = bank.items.index(short)
    bank.items[index] = short.model_copy(update={"required_points": ("Quidditch trophy",)})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("required point is not supported" in error for error in validation.errors)


def test_validate_bank_rejects_source_ref_outside_material() -> None:
    bank, pack, chunks = _bank()
    ref_two = _ref(chunks["b3-c07-0002"], TEXT_TWO[:40])
    bank.items[0] = _mcq(ref_two)
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("is not in the material" in error for error in validation.errors)


def test_validate_bank_rejects_answer_position_over_cap() -> None:
    bank, pack, chunks = _bank()
    ref_one = _ref(chunks["b3-c07-0001"], TEXT_ONE[:40])
    bank.items = [
        _mcq(ref_one).model_copy(
            update={
                "item_id": f"dada-mcq-{index:03d}",
                "prompt": f"Sample lesson question {index}?",
            }
        )
        for index in range(5)
    ]
    bank.manifest = bank.manifest.model_copy(
        update={"mcq_count": 5, "short_answer_count": 0}
    )
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("answer position" in error for error in validation.errors)


def test_structure_record_has_ids_not_prompts() -> None:
    bank, pack, chunks = _bank()
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    record = structure_record(bank, validation)
    assert "dada-mcq-001" in record
    assert "Which charm turns a boggart" not in record
    assert "Riddikulus" not in record


def test_structure_record_failure_omits_item_messages() -> None:
    bank, pack, chunks = _bank()
    short = next(item for item in bank.items if item.kind == "short_answer")
    index = bank.items.index(short)
    bank.items[index] = short.model_copy(update={"required_points": ("Quidditch trophy",)})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    record = structure_record(bank, validation)
    assert "Quidditch trophy" not in record
    assert "Detailed messages stay in the CLI output" in record


def test_store_refuses_published_replace(tmp_path: Path) -> None:
    bank, _, _ = _bank()
    with ExamStore(tmp_path / "exams.db") as store:
        store.replace_bank(bank)
        with pytest.raises(ValueError, match="published"):
            store.replace_bank(bank)
        store.replace_bank(bank, force=True)


def test_validate_bank_rejects_stale_pack_pin() -> None:
    bank, pack, chunks = _bank()
    bank.manifest = bank.manifest.model_copy(update={"pack_fingerprint": "stale"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("pack_fingerprint is stale" in error for error in validation.errors)


def test_validate_bank_rejects_stale_source_hash() -> None:
    bank, pack, chunks = _bank()
    item = bank.items[0]
    bad_ref = item.source_refs[0].model_copy(update={"text_hash": "stale"})
    bank.items[0] = item.model_copy(update={"source_refs": (bad_ref,)})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("text hash mismatch" in error for error in validation.errors)


def test_validate_bank_rejects_unknown_material() -> None:
    bank, pack, chunks = _bank()
    bank.items[0] = bank.items[0].model_copy(update={"material_id": "missing"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("unknown material" in error for error in validation.errors)


def test_validate_bank_rejects_duplicate_prompt() -> None:
    bank, pack, chunks = _bank()
    duplicate = bank.items[0].model_copy(update={"item_id": "dada-mcq-003"})
    bank.items.append(duplicate)
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("duplicate prompt" in error for error in validation.errors)


def test_published_bank_requires_reviewed_items() -> None:
    bank, pack, chunks = _bank()
    bank.items[0] = bank.items[0].model_copy(update={"review_status": "draft"})
    validation = validate_bank(bank, pack, chunks, INDEX_HASH)
    assert not validation.ok
    assert any("unreviewed item" in error for error in validation.errors)


def test_load_rejects_duplicate_item_ids(tmp_path: Path) -> None:
    bank, _, _ = _bank()
    directory = tmp_path / "dada"
    write_exam_bank(bank, directory)
    with (directory / "bank.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(bank.items[0].model_dump_json() + "\n")
    with pytest.raises(ValueError, match="duplicate item id"):
        load_exam_bank(directory)
