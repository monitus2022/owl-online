"""Tests for the exam-bank coverage report (#188)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from app.knowledge.materials import Material
from app.knowledge.packs import Concept, PackManifest, SubjectPack, Topic

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bank_coverage.py"
SPEC = importlib.util.spec_from_file_location("bank_coverage", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bank_coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bank_coverage)


def _pack() -> SubjectPack:
    return SubjectPack(
        manifest=PackManifest(subject="dada", version="test"),
        topics=[Topic(topic_id="topic", subject="dada", title="Topic")],
        concepts=[
            Concept(
                concept_id="dada-creature-pixie",
                subject="dada",
                kind="creature",
                title="Pixies",
                aliases=("Cornish pixie",),
            )
        ],
        materials=[
            Material(
                material_id="dada-test-material",
                subject="dada",
                topic="topic",
                concept="dada-creature-pixie",
                kind="creature",
                text="The Cornish pixie is small. A hinkypunk lures travellers.",
                review_status="reviewed",
            )
        ],
    )


def test_content_tokens_and_jaccard() -> None:
    left = bank_coverage.content_tokens("The boggart fears the dark")
    right = bank_coverage.content_tokens("A boggart fears a dark room")
    assert "the" not in left
    assert bank_coverage.jaccard(left, right) > 0.5


def test_gap_rows_marks_material_mentions_and_dedupes(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds.jsonl"
    rows = [
        {
            "concept_id": "dada-creature-cornish-pixie",
            "subject": "dada",
            "kind": "creature",
            "title": "Cornish pixie",
            "source_refs": [{"chunk_id": "b1-c01-0001"}],
            "basis": "taught-in-class",
        },
        {
            "concept_id": "dada-creature-hinkypunk",
            "subject": "dada",
            "kind": "creature",
            "title": "Hinkypunk",
            "source_refs": [{"chunk_id": "b1-c01-0002"}],
            "basis": "taught-in-class",
        },
        {
            "concept_id": "dada-creature-centaur",
            "subject": "dada",
            "kind": "creature",
            "title": "Centaurs",
            "source_refs": [{"chunk_id": "b1-c01-0003"}],
            "basis": "taught-in-class",
        },
        {
            "concept_id": "dada-creature-centaur",
            "subject": "dada",
            "kind": "creature",
            "title": "Centaurs duplicate",
            "source_refs": [],
            "basis": "taught-in-class",
        },
        {
            "concept_id": "dada-event-battle-of-hogwarts",
            "subject": "dada",
            "kind": "event",
            "title": "Battle of Hogwarts",
            "source_refs": [],
            "basis": "author-pick",
        },
        {
            "concept_id": "dada-magic-transfiguration",
            "subject": "dada",
            "kind": "spell",
            "title": "Transfiguration",
            "source_refs": [{"chunk_id": "b1-c01-0004"}],
            "basis": "taught-in-class",
        },
    ]
    seeds.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    gaps = {row["concept"]: row for row in bank_coverage.gap_rows(_pack(), seeds)}

    assert "dada-creature-cornish-pixie" not in gaps
    assert gaps["dada-creature-hinkypunk"]["mentioned_in_material"] is True
    assert gaps["dada-creature-centaur"]["mentioned_in_material"] is False
    assert gaps["dada-creature-centaur"]["refs"] == 1
    assert gaps["dada-event-battle-of-hogwarts"]["refs"] == 0
    assert "dada-magic-transfiguration" not in gaps
