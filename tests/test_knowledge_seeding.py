"""Seeding (#128): canon index x approved lesson tables -> concept drafts."""

import json
from pathlib import Path

import pytest

from app.knowledge.seeding import build_seeds, load_lesson_table, write_bundle


def _wl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Path]:
    lesson = tmp_path / "dada.jsonl"
    _wl(lesson, [
        {"book": 3, "chapter": 7, "subject": "dada", "teacher": "Lupin",
         "basis": "taught-in-class", "reason": "", "status": "approved"},
        {"book": 5, "chapter": 18, "subject": "dada", "teacher": "Umbridge",
         "basis": "author-pick", "reason": "DA practical", "status": "approved"},
    ])
    canon = tmp_path / "canon_index.jsonl"
    _wl(canon, [
        {"entry_key": "magic/boggart-banishing-spell", "family": "magic",
         "title": "Boggart Banishing Spell", "book": 3, "chapter": 7,
         "epilogue": False, "agreement": "both", "sources": ["article"],
         "low_precision": False, "total_hits": 1,
         "candidates": [{"chunk_id": "b3-c07-0056", "text_hash": "aa11",
                         "span": [10, 20], "phrase": "Riddikulus"}]},
        {"entry_key": "magic/boggart-banishing-spell", "family": "magic",
         "title": "Boggart Banishing Spell", "book": 5, "chapter": 18,
         "epilogue": False, "agreement": "forward-only",
         "sources": ["article"], "low_precision": False, "total_hits": 1,
         "candidates": [{"chunk_id": "b5-c18-0001", "text_hash": "bb22",
                         "span": [0, 9], "phrase": "Riddikulus"}]},
        {"entry_key": "creature/dementors", "family": "creature",
         "title": "Dementors", "book": 3, "chapter": 10, "epilogue": False,
         "agreement": "both", "sources": ["article"], "low_precision": False,
         "total_hits": 2,
         "candidates": [{"chunk_id": "b3-c10-0016", "text_hash": "cc33",
                         "span": [5, 15], "phrase": "dementors"}]},
        {"entry_key": "magic/draught-of-peace", "family": "magic",
         "title": "Draught of Peace", "book": 6, "chapter": None,
         "epilogue": False, "agreement": "both", "sources": ["article"],
         "low_precision": False, "total_hits": 0, "candidates": []},
        {"entry_key": "magic/accio", "family": "magic", "title": "Summoning Charm",
         "book": 5, "chapter": 18, "epilogue": False, "agreement": "reverse-only",
         "sources": ["tab"], "low_precision": False, "total_hits": 0,
         "candidates": []},
    ])
    entries = tmp_path / "entries.jsonl"
    _wl(entries, [
        {"family": "magic", "slug": "boggart-banishing-spell",
         "url": "https://www.hp-lexicon.org/magic/boggart-banishing-spell/",
         "title": "Boggart Banishing Spell", "incantation": "Riddikulus"},
        {"family": "creature", "slug": "dementors",
         "url": "https://www.hp-lexicon.org/creature/dementors/",
         "title": "Dementors", "incantation": ""},
        {"family": "magic", "slug": "accio",
         "url": "https://www.hp-lexicon.org/magic/accio/",
         "title": "Summoning Charm", "incantation": "Accio"},
    ])
    fetch = tmp_path / "fetch_index.jsonl"
    _wl(fetch, [
        {"url": "https://www.hp-lexicon.org/magic/boggart-banishing-spell/",
         "fetched_at": "2026-11-08T01:00:00+00:00"},
        {"url": "https://www.hp-lexicon.org/creature/dementors/",
         "fetched_at": "2026-11-08T01:05:00+00:00"},
    ])
    return {"lesson": lesson, "canon": canon, "entries": entries, "fetch": fetch}


def _build(tmp_path: Path):
    fx = _fixture(tmp_path)
    return build_seeds(
        "dada", fx["canon"], fx["lesson"], fx["entries"], fx["fetch"],
        index_text_hash="aca4c57462d449f5",
    )


def test_lesson_table_rejects_unapproved(tmp_path: Path):
    p = tmp_path / "t.jsonl"
    _wl(p, [{"book": 3, "chapter": 7, "subject": "dada", "teacher": "Lupin",
             "basis": "taught-in-class", "status": "draft"}])
    with pytest.raises(ValueError, match="not approved"):
        load_lesson_table(p)


def test_seeds_follow_approved_chapters(tmp_path: Path):
    bundle = _build(tmp_path)
    titles = {c.title for c in bundle.concepts}
    assert titles == {"Boggart Banishing Spell", "Summoning Charm"}
    assert bundle.lesson_chapters == 2
    assert bundle.book_level_skipped == 1
    # dementors edge (b3c10) is outside the approved table -> queue, not seed
    assert [u["entry_key"] for u in bundle.unassigned] == ["creature/dementors"]
    assert bundle.unassigned[0]["verified"] == 1


def test_concept_prefill_and_precedence(tmp_path: Path):
    bundle = _build(tmp_path)
    boggart = next(c for c in bundle.concepts if c.concept_id.endswith(
        "magic-boggart-banishing-spell"))
    assert boggart.kind == "spell"
    assert boggart.aliases == ("Riddikulus",)
    assert boggart.basis == "taught-in-class"  # outranks the DA author-pick row
    assert boggart.teacher == "Lupin"
    assert {r.chunk_id for r in boggart.source_refs} == {
        "b3-c07-0056", "b5-c18-0001"}
    assert all(r.index_text_hash == "aca4c57462d449f5" for r in boggart.source_refs)
    assert boggart.agreement["both"] == 1
    assert boggart.reference is not None
    assert boggart.reference.publisher == "The Harry Potter Lexicon"
    assert boggart.reference.accessed.isoformat() == "2026-11-08"


def test_unresolved_entry_still_seeds_as_hint(tmp_path: Path):
    bundle = _build(tmp_path)
    accio = next(c for c in bundle.concepts if c.title == "Summoning Charm")
    assert accio.source_refs == ()
    assert accio.agreement["reverse-only"] == 1
    # no fetch record -> reference omitted rather than fabricated
    assert accio.reference is None


def test_write_bundle_round_trips(tmp_path: Path):
    bundle = _build(tmp_path)
    out = write_bundle(bundle, tmp_path / "seeds")
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["subject"] == "dada"
    queue = (tmp_path / "seeds" / "queue_unassigned.jsonl").read_text()
    assert "creature/dementors" in queue


def test_stats(tmp_path: Path):
    stats = _build(tmp_path).stats()
    assert stats["concepts"] == 2
    assert stats["resolved_with_evidence"] == 1
    assert stats["edges_seen"] == 5
