"""Subject-pack tests: taxonomy, model rules, storage round-trip, validation.

All fixtures are invented (a fictional "Levitation Basics" DADA mini-pack over
synthetic chunks). No copyrighted corpus text: the validator is exercised
against synthetic `Chunk` objects whose text hashes and quotes are computed in
the test, so the corpus join is checked without the real books.
"""


import pytest
from pydantic import ValidationError

from app.knowledge.materials import Material, ReferenceLink, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    SubjectPack,
    Topic,
    index_chunks,
    load_subject_pack,
    pack_fingerprint,
    validate_pack,
    write_subject_pack,
)
from app.knowledge.taxonomy import SUBJECTS, known_subject
from app.schemas import Chunk, ChunkMetadata

INDEX_HASH = "a" * 16


def _chunk(cid: str, text: str, book: int, chapter: int) -> Chunk:
    return Chunk(
        id=cid,
        text=text,
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=chapter,
            book_name=f"Book {book}",
            chapter_name=f"Chapter {chapter}",
        ),
    )


def _ref_for(chunk: Chunk, quote: str) -> SourceRef:
    return SourceRef(
        chunk_id=chunk.id,
        book=chunk.metadata.book_num,
        chapter=chunk.metadata.chapter_num,
        quote=quote,
        text_hash=chunk_text_hash(chunk.text),
        index_text_hash=INDEX_HASH,
    )


def _material(source_refs: list[SourceRef] | None = None) -> Material:
    return Material(
        material_id="dada.levitation.01",
        subject="dada",
        topic="dada.levitation",
        concept="dada.levitation",
        kind="spell",
        text="A counter-jinx lifts a feather against a downward hex.",
        source_refs=source_refs if source_refs is not None else [],
    )


def _pack(chunks: list[Chunk]) -> SubjectPack:
    chunk = chunks[0]
    return SubjectPack(
        manifest=PackManifest(
            subject="dada", version="v1", status="draft", index_text_hash=INDEX_HASH
        ),
        topics=[Topic(topic_id="dada.levitation", subject="dada", title="Levitation Basics")],
        concepts=[
            Concept(
                concept_id="dada.levitation",
                subject="dada",
                kind="spell",
                title="Levitation Charm",
            )
        ],
        materials=[_material([_ref_for(chunk, "laughter")])],
    )


# --- taxonomy ---------------------------------------------------------------


def test_twelve_subjects_and_dada_key():
    assert len(SUBJECTS) == 12
    assert known_subject("dada") is not None
    assert known_subject("astronomy") is not None
    assert known_subject("divination") is not None
    assert known_subject("defence") is None


def test_subject_keys_are_unique():
    keys = [key for key, _ in SUBJECTS]
    assert len(keys) == len(set(keys))


# --- model rules ------------------------------------------------------------


def test_primary_material_must_be_books_scoped():
    base = _material().model_dump(exclude={"canon_tier", "canon_scope"})
    with pytest.raises(ValidationError):
        Material(**base, canon_tier="primary", canon_scope="films")
    # A secondary fact may be film-scoped.
    Material(**base, canon_tier="secondary", canon_scope="films")


def test_source_ref_shape_rules():
    with pytest.raises(ValidationError):
        SourceRef(
            chunk_id="bad-id", book=1, chapter=1, quote="q", text_hash="h", index_text_hash="i"
        )
    with pytest.raises(ValidationError):
        SourceRef(
            chunk_id="b8-c01-0000", book=8, chapter=1, quote="q", text_hash="h", index_text_hash="i"
        )
    with pytest.raises(ValidationError):
        SourceRef(
            chunk_id="b1-c01-0000",
            book=1,
            chapter=1,
            quote="   ",
            text_hash="h",
            index_text_hash="i",
        )


def test_reference_link_needs_absolute_url_and_accessed():
    with pytest.raises(ValidationError):
        ReferenceLink(
            title="Entry", url="hp-lexicon.org/x", publisher="Lexicon", accessed="2026-11-08"
        )
    link = ReferenceLink(
        title="Entry", url="https://hp-lexicon.org/x", publisher="Lexicon", accessed="2026-11-08"
    )
    assert link.accessed.year == 2026


def test_material_rejects_unknown_kind_and_id():
    base = _material().model_dump()
    with pytest.raises(ValidationError):
        Material(**{**base, "kind": "vehicle"})
    with pytest.raises(ValidationError):
        Material(**{**base, "material_id": "Bad ID"})


def test_chunk_text_hash_is_short_hex():
    digest = chunk_text_hash("the wand moved")
    assert len(digest) == 16
    assert all(c in "0123456789abcdef" for c in digest)
    assert chunk_text_hash("the wand moved") == digest


# --- storage round-trip -----------------------------------------------------


def test_write_and_load_round_trip(tmp_path):
    chunk = _chunk("b3-c08-0001", "boggart banished by laughter", 3, 8)
    pack = _pack([chunk])
    directory = tmp_path / "dada"
    write_subject_pack(pack, directory)
    loaded = load_subject_pack(directory)
    assert loaded.manifest.subject == "dada"
    assert [t.topic_id for t in loaded.topics] == ["dada.levitation"]
    assert loaded.find_material("dada.levitation.01") is not None
    assert loaded.materials[0].source_refs[0].chunk_id == "b3-c08-0001"


def test_load_fails_on_missing_manifest(tmp_path):
    with pytest.raises(ValueError, match="pack.toml"):
        load_subject_pack(tmp_path)


def test_load_rejects_unknown_subject(tmp_path):
    directory = tmp_path / "x"
    directory.mkdir()
    (directory / "pack.toml").write_text('subject = "not-a-subject"\nversion = "v1"\n')
    with pytest.raises(ValueError):
        load_subject_pack(directory)


def test_load_rejects_material_citing_unknown_topic(tmp_path):
    chunk = _chunk("b3-c08-0001", "text", 3, 8)
    pack = _pack([chunk])
    bad = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"topic": "nope"})]}
    )
    directory = tmp_path / "dada"
    write_subject_pack(bad, directory)
    with pytest.raises(ValueError, match="unknown topic"):
        load_subject_pack(directory)


# --- fingerprint (rebuild reproducibility) ----------------------------------


def test_fingerprint_stable_across_field_and_meta_order(tmp_path):
    chunk = _chunk("b3-c08-0001", "text", 3, 8)
    pack = _pack([chunk])
    reordered = pack.model_copy(
        update={
            "manifest": pack.manifest.model_copy(
                update={"version": "v2", "built_at": "2026-11-08", "status": "published"}
            )
        }
    )
    assert pack_fingerprint(pack) == pack_fingerprint(reordered)


def test_fingerprint_changes_when_a_material_changes():
    chunk = _chunk("b3-c08-0001", "text", 3, 8)
    pack = _pack([chunk])
    edited = pack.model_copy(
        update={
            "materials": [
                pack.materials[0].model_copy(update={"text": "different grounded text"})
            ]
        }
    )
    assert pack_fingerprint(pack) != pack_fingerprint(edited)


# --- validation against the corpus -----------------------------------------


def test_valid_pack_resolves_and_reports_coverage():
    chunk = _chunk("b3-c08-0001", "a boggart is banished by laughter", 3, 8)
    pack = _pack([chunk])
    result = validate_pack(pack, index_chunks([chunk]), INDEX_HASH)
    assert result.ok, result.errors
    assert result.coverage.valid_materials == 1
    assert result.coverage.per_topic_with_source["dada.levitation"] == 1
    assert result.coverage.concepts_without_material == []


def test_draft_review_status_warns_but_is_not_an_error():
    chunk = _chunk("b3-c08-0001", "laughter banishes a boggart", 3, 8)
    pack = _pack([chunk])  # review_status defaults to draft
    result = validate_pack(pack, index_chunks([chunk]), INDEX_HASH)
    assert result.ok
    assert any("review_status=draft" in w for w in result.warnings)


def test_material_without_source_refs_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    bare = pack.model_copy(update={"materials": [_material([])]})
    result = validate_pack(bare, index_chunks([chunk]), INDEX_HASH)
    assert not result.ok
    assert any("no source refs" in e for e in result.errors)


def test_orphan_concept_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    extra = pack.concepts[0].model_copy(
        update={"concept_id": "dada.patronus", "title": "Patronus"}
    )
    with_concepts = pack.model_copy(update={"concepts": [*pack.concepts, extra]})
    result = validate_pack(with_concepts, index_chunks([chunk]), INDEX_HASH)
    assert not result.ok
    assert any("orphan concept" in e for e in result.errors)


def test_text_hash_mismatch_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    stale_ref = pack.materials[0].source_refs[0].model_copy(
        update={"text_hash": "deadbeef00000000"}
    )
    broken = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"source_refs": [stale_ref]})]}
    )
    result = validate_pack(broken, index_chunks([chunk]), INDEX_HASH)
    assert not result.ok
    assert any("text hash mismatch" in e for e in result.errors)


def test_quote_not_in_chunk_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    bad_ref = pack.materials[0].source_refs[0].model_copy(update={"quote": "not present"})
    broken = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"source_refs": [bad_ref]})]}
    )
    result = validate_pack(broken, index_chunks([chunk]), INDEX_HASH)
    assert any("quote not found" in e for e in result.errors)


def test_book_chapter_metadata_mismatch_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    moved = pack.materials[0].source_refs[0].model_copy(update={"chapter": 9})
    broken = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"source_refs": [moved]})]}
    )
    result = validate_pack(broken, index_chunks([chunk]), INDEX_HASH)
    assert any("chapter" in e and "but the chunk is" in e for e in result.errors)


def test_missing_chunk_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    result = validate_pack(pack, {}, INDEX_HASH)
    assert any("not in corpus" in e for e in result.errors)


def test_stale_index_hash_flags_whole_pack():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    result = validate_pack(pack, index_chunks([chunk]), "b" * 16)
    assert not result.ok
    assert any("index hash" in e for e in result.errors)


def test_fingerprint_serializes_references():
    """The blocker regression: a date-valued ReferenceLink must serialize in
    the fingerprint instead of raising TypeError."""
    from app.knowledge.materials import ReferenceLink

    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    linked = pack.model_copy(
        update={
            "materials": [
                pack.materials[0].model_copy(
                    update={
                        "references": [
                            ReferenceLink(
                                title="Boggart Banishing Spell",
                                url="https://www.hp-lexicon.org/magic/boggart-banishing-spell/",
                                publisher="The Harry Potter Lexicon",
                                accessed="2026-11-08",
                            )
                        ]
                    }
                )
            ]
        }
    )
    assert len(pack_fingerprint(linked)) == 16


def test_references_round_trip_through_storage(tmp_path):
    from app.knowledge.materials import ReferenceLink

    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    link = ReferenceLink(
        title="Entry",
        url="https://www.hp-lexicon.org/magic/entry/",
        publisher="The Harry Potter Lexicon",
        accessed="2026-11-08",
    )
    with_link = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"references": [link]})]}
    )
    directory = tmp_path / "dada"
    write_subject_pack(with_link, directory)
    loaded = load_subject_pack(directory)
    assert loaded.materials[0].references[0].accessed.isoformat() == "2026-11-08"
    assert pack_fingerprint(loaded) == pack_fingerprint(with_link)


def test_non_primary_material_may_not_carry_source_refs():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    secondary = pack.materials[0].model_copy(
        update={"canon_tier": "secondary", "canon_scope": "films"}
    )
    padded = pack.model_copy(update={"materials": [secondary]})
    result = validate_pack(padded, index_chunks([chunk]), INDEX_HASH)
    assert any("may not carry source refs" in e for e in result.errors)


def test_extra_fields_are_rejected_not_dropped():
    """Policy hardening: prose smuggled onto a ReferenceLink fails loudly."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ReferenceLink(
            title="Entry",
            url="https://www.hp-lexicon.org/magic/entry/",
            publisher="The Harry Potter Lexicon",
            accessed="2026-11-08",
            text="copied lexicon prose",
        )


def test_kind_mismatch_between_material_and_concept_is_an_error():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    wrong = pack.model_copy(
        update={
            "concepts": [pack.concepts[0].model_copy(update={"kind": "creature"})],
            "materials": [pack.materials[0].model_copy(update={"kind": "creature"})],
        }
    )
    # kinds now agree (creature/creature): still valid.
    assert validate_pack(wrong, index_chunks([chunk]), INDEX_HASH).ok
    mismatched = pack.model_copy(
        update={"concepts": [pack.concepts[0].model_copy(update={"kind": "creature"})]}
    )
    result = validate_pack(mismatched, index_chunks([chunk]), INDEX_HASH)
    assert any("kind" in e for e in result.errors)


def test_empty_topic_appears_in_coverage():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    extra_topic = pack.topics[0].model_copy(
        update={"topic_id": "dada.shielding", "title": "Shielding"}
    )
    widened = pack.model_copy(update={"topics": [*pack.topics, extra_topic]})
    result = validate_pack(widened, index_chunks([chunk]), INDEX_HASH)
    assert result.ok
    assert result.coverage.per_topic["dada.shielding"] == 0
    assert result.coverage.per_topic_with_source.get("dada.shielding") is None


def test_short_quote_warns():
    chunk = _chunk("b3-c08-0001", "laughter banishes it", 3, 8)
    pack = _pack([chunk])
    tiny = pack.materials[0].source_refs[0].model_copy(update={"quote": "it"})
    shortened = pack.model_copy(
        update={"materials": [pack.materials[0].model_copy(update={"source_refs": [tiny]})]}
    )
    result = validate_pack(shortened, index_chunks([chunk]), INDEX_HASH)
    assert result.ok
    assert any("quote under three words" in w for w in result.warnings)


def test_epilogue_chapter_hint_and_non_ascii_manifest_round_trip(tmp_path):
    ref = _ref_for(_chunk("b7-c36-0103", "the scar had not pained him", 7, 36), "scar")
    assert ref.in_epilogue_chapter
    assert not ref.model_copy(update={"chunk_id": "b7-c35-0002"}).in_epilogue_chapter
    pack = _pack([_chunk("b3-c08-0001", "laughter", 3, 8)])
    unicode_manifest = pack.manifest.model_copy(update={"version": "v1 — prénom"})
    packed = pack.model_copy(update={"manifest": unicode_manifest})
    write_subject_pack(packed, tmp_path / "dada")
    loaded = load_subject_pack(tmp_path / "dada")
    assert loaded.manifest.version == "v1 — prénom"


def test_published_pack_requires_reviewed_material():
    chunk = _chunk("b3-c08-0001", "laughter", 3, 8)
    pack = _pack([chunk])
    published = pack.model_copy(
        update={"manifest": pack.manifest.model_copy(update={"status": "published"})}
    )
    result = validate_pack(published, index_chunks([chunk]), INDEX_HASH)
    assert not result.ok
    assert any("unreviewed material" in e for e in result.errors)
    reviewed = published.model_copy(
        update={
            "materials": [
                published.materials[0].model_copy(update={"review_status": "reviewed"})
            ]
        }
    )
    assert validate_pack(reviewed, index_chunks([chunk]), INDEX_HASH).ok
