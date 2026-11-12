"""Build the committed lesson and multi-turn RAG fixtures from published packs.

The fixtures store concept titles, material ids and source-ref structure only.
They never store material prose, source quotes or corpus text.

Run:
    uv run python scripts/build_rag_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.materials import Material  # noqa: E402
from app.knowledge.packs import SubjectPack, load_subject_pack  # noqa: E402

SUBJECTS = ("dada", "charms", "potions", "transfiguration", "herbology")

# Six curated concept titles per subject: four single questions, two
# paraphrases, and four multi-concept pairs. Titles must exist in the pack.
TITLES = {
    "dada": (
        "Boggart",
        "Dementors",
        "Disarming Charm",
        "Patronus",
        "Fidelius Charm",
        "Werewolves",
    ),
    "charms": (
        "Levitation Charm",
        "Wand-Lighting Charm",
        "Wand-Extinguishing Charm",
        "Summoning Charm",
        "Unlocking Charm",
        "Mending Charm",
    ),
    "potions": (
        "Felix Felicis",
        "Veritaserum",
        "Polyjuice Potion",
        "Draught of Peace",
        "Mandrake Restorative Draught",
        "Bezoar",
    ),
    "transfiguration": (
        "Animagus",
        "Metamorphmagus",
        "Vanishing Spell",
        "Conjuring",
        "Gamp's Law of Elemental Transfiguration",
        "Switching Spell",
    ),
    "herbology": (
        "Mandrake",
        "Devil's Snare",
        "Gillyweed",
        "Venomous Tentacula",
        "Whomping Willow",
        "Bubotuber",
    ),
}

# Invented terms that do not name a published concept or a corpus entity.
ABSTAIN = {
    "dada": ("Vellumbra", "Quorith"),
    "charms": ("Sablewing", "Pellucid"),
    "potions": ("Threnody", "Morrowglass"),
    "transfiguration": ("Kestrelglass", "Orrin's Fold"),
    "herbology": ("Sorrowroot", "Glimmercap"),
}

PAIRS = ((0, 1), (2, 3), (4, 5), (0, 2))


def _materials_for(pack: SubjectPack, title: str) -> list[Material]:
    concept_ids = {concept.concept_id for concept in pack.concepts if concept.title == title}
    materials = [m for m in pack.materials if m.concept in concept_ids]
    if not materials:
        raise ValueError(f"{pack.manifest.subject}: no material for {title!r}")
    return materials


def _source_refs(materials: list[Material]) -> list[dict[str, object]]:
    seen: set[str] = set()
    refs: list[dict[str, object]] = []
    for material in materials:
        for ref in material.source_refs:
            if ref.chunk_id in seen:
                continue
            seen.add(ref.chunk_id)
            refs.append({"chunk_id": ref.chunk_id, "book": ref.book, "chapter": ref.chapter})
    return refs


def _lesson_item(
    *,
    subject: str,
    index: int,
    question: str,
    slice_name: str,
    materials: list[Material],
    answerable: bool,
    note: str,
    groups: list[tuple[str, list[Material]]] | None = None,
    expected_chunk_ids: tuple[str, ...] = (),
    expected_scope: str | None = None,
    citation: str | None = None,
) -> dict[str, object]:
    if groups is None and materials:
        groups = [("expected", materials)]
    expected_groups = [
        {
            "title": title,
            "material_ids": sorted({material.material_id for material in group}),
        }
        for title, group in (groups or [])
    ]
    return {
        "id": f"lesson-{subject}-{index:02d}",
        "subject": subject,
        "question": question,
        "slice": slice_name,
        "answerable": answerable,
        "expected_scope": expected_scope or ("in_pack" if answerable else "abstained"),
        "citation": citation or ("material" if answerable else "none"),
        "expected_material_ids": sorted({m.material_id for m in materials}),
        "expected_source_refs": _source_refs(materials),
        "expected_groups": expected_groups,
        "expected_chunk_ids": list(expected_chunk_ids),
        "note": note,
    }


def _turn(
    *,
    question: str,
    mode: str,
    expected_standalone: str,
    expected_mode: str,
    materials: list[Material] | None = None,
    groups: list[tuple[str, list[Material]]] | None = None,
    expected_abstained: bool | None = False,
    referral: tuple[str, str] | None = None,
    note: str = "",
) -> dict[str, object]:
    if groups is None and materials:
        groups = [("expected", materials)]
    expected_groups = [
        {
            "title": title,
            "material_ids": sorted({material.material_id for material in group}),
        }
        for title, group in (groups or [])
    ]
    return {
        "question": question,
        "mode": mode,
        "expected_standalone": expected_standalone,
        "expected_mode": expected_mode,
        "expected_material_ids": sorted({m.material_id for m in (materials or [])}),
        "expected_groups": expected_groups,
        "expected_abstained": expected_abstained,
        "expected_referral_subject": referral[0] if referral else None,
        "expected_referral_concept": referral[1] if referral else None,
        "note": note,
    }


def _conversation(
    *,
    conversation_id: str,
    subject: str,
    slice_name: str,
    turns: list[dict[str, object]],
    note: str,
) -> dict[str, object]:
    return {
        "id": conversation_id,
        "subject": subject,
        "slice": slice_name,
        "turns": turns,
        "note": note,
    }


def build() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    packs = {
        subject: load_subject_pack(REPO / "data" / "subjects" / subject) for subject in SUBJECTS
    }
    groups = {
        subject: {title: _materials_for(packs[subject], title) for title in titles}
        for subject, titles in TITLES.items()
    }

    def materials(subject: str, title: str) -> list[Material]:
        if title in groups[subject]:
            return groups[subject][title]
        return _materials_for(packs[subject], title)

    def groups_for(subject: str, *titles: str) -> list[tuple[str, list[Material]]]:
        return [(title, materials(subject, title)) for title in titles]

    lesson: list[dict[str, object]] = []
    for subject, titles in TITLES.items():
        index = 0
        for title in titles[:4]:
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question=f"Tell me about {title}.",
                    slice_name="in_pack",
                    materials=groups[subject][title],
                    answerable=True,
                    note=f"single concept: {title}",
                )
            )
            index += 1
        for title in titles[4:]:
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question=f"Explain {title} as you would to a first-year.",
                    slice_name="paraphrase",
                    materials=groups[subject][title],
                    answerable=True,
                    note=f"paraphrase: {title}",
                )
            )
            index += 1
        for left, right in PAIRS:
            left_title, right_title = titles[left], titles[right]
            pair_materials = groups[subject][left_title] + groups[subject][right_title]
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question=f"Compare {left_title} with {right_title}.",
                    slice_name="multi_concept",
                    materials=pair_materials,
                    answerable=True,
                    note=f"multi concept: {left_title}; {right_title}",
                    groups=groups_for(subject, left_title, right_title),
                )
            )
            index += 1
        for term in ABSTAIN[subject]:
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question=f"What is {term}?",
                    slice_name="abstain",
                    materials=[],
                    answerable=False,
                    note=f"invented term: {term}",
                )
            )
            index += 1
        if subject == "dada":
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question="Compare Boggart with the Triwizard Tournament.",
                    slice_name="mixed",
                    materials=groups[subject]["Boggart"],
                    answerable=True,
                    note="mixed: Boggart plus corpus Triwizard evidence",
                    groups=groups_for(subject, "Boggart"),
                    expected_chunk_ids=(
                        "b4-c12-0001",
                        "b4-c12-0059",
                        "b4-c12-0063",
                        "b4-c12-0080",
                    ),
                    expected_scope="mixed",
                    citation="both",
                )
            )
            index += 1
            lesson.append(
                _lesson_item(
                    subject=subject,
                    index=index,
                    question="What is the name of the three-headed dog?",
                    slice_name="off_pack",
                    materials=[],
                    answerable=True,
                    note="off_pack: corpus-only question",
                    expected_chunk_ids=(
                        "b1-c11-0011",
                        "b1-c11-0042",
                        "b1-c12-0059",
                        "b1-c15-0018",
                    ),
                    expected_scope="off_pack",
                    citation="book",
                )
            )
            index += 1

    conversations = [
        _conversation(
            conversation_id="mt-dada-comparison",
            subject="dada",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Boggart.",
                    mode="lesson",
                    expected_standalone="Tell me about Boggart.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart"),
                ),
                _turn(
                    question="what about Dementors?",
                    mode="lesson",
                    expected_standalone="Compare Boggart with Dementors.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart") + materials("dada", "Dementors"),
                    groups=groups_for("dada", "Boggart", "Dementors"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-charms-comparison",
            subject="charms",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Wand-Lighting Charm.",
                    mode="lesson",
                    expected_standalone="Tell me about Wand-Lighting Charm.",
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Lighting Charm"),
                ),
                _turn(
                    question="what about Wand-Extinguishing Charm?",
                    mode="lesson",
                    expected_standalone=(
                        "Compare Wand-Lighting Charm with Wand-Extinguishing Charm."
                    ),
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Lighting Charm")
                    + materials("charms", "Wand-Extinguishing Charm"),
                    groups=groups_for("charms", "Wand-Lighting Charm", "Wand-Extinguishing Charm"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-potions-comparison",
            subject="potions",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Felix Felicis.",
                    mode="lesson",
                    expected_standalone="Tell me about Felix Felicis.",
                    expected_mode="lesson",
                    materials=materials("potions", "Felix Felicis"),
                ),
                _turn(
                    question="what about Veritaserum?",
                    mode="lesson",
                    expected_standalone="Compare Felix Felicis with Veritaserum.",
                    expected_mode="lesson",
                    materials=materials("potions", "Felix Felicis")
                    + materials("potions", "Veritaserum"),
                    groups=groups_for("potions", "Felix Felicis", "Veritaserum"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-transfiguration-comparison",
            subject="transfiguration",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Animagus.",
                    mode="lesson",
                    expected_standalone="Tell me about Animagus.",
                    expected_mode="lesson",
                    materials=materials("transfiguration", "Animagus"),
                ),
                _turn(
                    question="what about Metamorphmagus?",
                    mode="lesson",
                    expected_standalone="Compare Animagus with Metamorphmagus.",
                    expected_mode="lesson",
                    materials=materials("transfiguration", "Animagus")
                    + materials("transfiguration", "Metamorphmagus"),
                    groups=groups_for("transfiguration", "Animagus", "Metamorphmagus"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-herbology-comparison",
            subject="herbology",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Mandrake.",
                    mode="lesson",
                    expected_standalone="Tell me about Mandrake.",
                    expected_mode="lesson",
                    materials=materials("herbology", "Mandrake"),
                ),
                _turn(
                    question="what about Devil's Snare?",
                    mode="lesson",
                    expected_standalone="Compare Mandrake with Devil's Snare.",
                    expected_mode="lesson",
                    materials=materials("herbology", "Mandrake")
                    + materials("herbology", "Devil's Snare"),
                    groups=groups_for("herbology", "Mandrake", "Devil's Snare"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-dada-third-topic",
            subject="dada",
            slice_name="third_topic",
            turns=[
                _turn(
                    question="Tell me about Boggart.",
                    mode="lesson",
                    expected_standalone="Tell me about Boggart.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart"),
                ),
                _turn(
                    question="what about Dementors?",
                    mode="lesson",
                    expected_standalone="Compare Boggart with Dementors.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart") + materials("dada", "Dementors"),
                    groups=groups_for("dada", "Boggart", "Dementors"),
                ),
                _turn(
                    question="what about Patronus?",
                    mode="lesson",
                    expected_standalone="Compare Dementors with Patronus.",
                    expected_mode="lesson",
                    materials=materials("dada", "Dementors") + materials("dada", "Patronus"),
                    groups=groups_for("dada", "Dementors", "Patronus"),
                ),
            ],
            note="third topic chains from the second, not the first",
        ),
        _conversation(
            conversation_id="mt-charms-third-topic",
            subject="charms",
            slice_name="third_topic",
            turns=[
                _turn(
                    question="Tell me about Wand-Lighting Charm.",
                    mode="lesson",
                    expected_standalone="Tell me about Wand-Lighting Charm.",
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Lighting Charm"),
                ),
                _turn(
                    question="what about Wand-Extinguishing Charm?",
                    mode="lesson",
                    expected_standalone=(
                        "Compare Wand-Lighting Charm with Wand-Extinguishing Charm."
                    ),
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Lighting Charm")
                    + materials("charms", "Wand-Extinguishing Charm"),
                    groups=groups_for("charms", "Wand-Lighting Charm", "Wand-Extinguishing Charm"),
                ),
                _turn(
                    question="what about Unlocking Charm?",
                    mode="lesson",
                    expected_standalone=("Compare Wand-Extinguishing Charm with Unlocking Charm."),
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Extinguishing Charm")
                    + materials("charms", "Unlocking Charm"),
                    groups=groups_for("charms", "Wand-Extinguishing Charm", "Unlocking Charm"),
                ),
            ],
            note="third topic chains from the second",
        ),
        _conversation(
            conversation_id="mt-dada-pronoun",
            subject="dada",
            slice_name="pronoun",
            turns=[
                _turn(
                    question="Who is Professor Lupin?",
                    mode="answer",
                    expected_standalone="Who is Professor Lupin?",
                    expected_mode="answer",
                    expected_abstained=None,
                ),
                _turn(
                    question="who trained him?",
                    mode="answer",
                    expected_standalone="who trained Professor Lupin?",
                    expected_mode="answer",
                    expected_abstained=None,
                    note="pronoun resolves to the last person",
                ),
            ],
            note="cross-request pronoun resolution",
        ),
        _conversation(
            conversation_id="mt-dada-implicit",
            subject="dada",
            slice_name="implicit_referent",
            turns=[
                _turn(
                    question="Tell me about Boggart.",
                    mode="lesson",
                    expected_standalone="Tell me about Boggart.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart"),
                ),
                _turn(
                    question="how do I defeat one?",
                    mode="lesson",
                    expected_standalone="How do I defeat a Boggart?",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart Banishing Spell")
                    + materials("dada", "Boggart"),
                    groups=groups_for("dada", "Boggart Banishing Spell"),
                    expected_abstained=False,
                    note="target behaviour: resolve 'one' before retrieval",
                ),
            ],
            note="implicit referent, currently expected to fail",
        ),
        _conversation(
            conversation_id="mt-dada-correction",
            subject="dada",
            slice_name="correction",
            turns=[
                _turn(
                    question="Tell me about Boggart.",
                    mode="lesson",
                    expected_standalone="Tell me about Boggart.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart"),
                ),
                _turn(
                    question="no, I meant a Dementor",
                    mode="lesson",
                    expected_standalone="Tell me about a Dementor.",
                    expected_mode="lesson",
                    materials=materials("dada", "Dementors"),
                    expected_abstained=False,
                    note="target behaviour: correction replaces the topic",
                ),
            ],
            note="correction, currently expected to fail on the rewrite",
        ),
        _conversation(
            conversation_id="mt-dada-off-topic",
            subject="dada",
            slice_name="off_topic",
            turns=[
                _turn(
                    question="Tell me about Boggart.",
                    mode="lesson",
                    expected_standalone="Tell me about Boggart.",
                    expected_mode="lesson",
                    materials=materials("dada", "Boggart"),
                ),
                _turn(
                    question="What is the capital of France?",
                    mode="lesson",
                    expected_standalone="What is the capital of France?",
                    expected_mode="abstain",
                    expected_abstained=True,
                ),
            ],
            note="off-topic turn must not inherit the previous topic",
        ),
        _conversation(
            conversation_id="mt-cross-dada-charms",
            subject="dada",
            slice_name="cross_subject",
            turns=[
                _turn(
                    question="Tell me about Disarming Charm.",
                    mode="lesson",
                    expected_standalone="Tell me about Disarming Charm.",
                    expected_mode="lesson",
                    materials=materials("dada", "Disarming Charm"),
                ),
                _turn(
                    question="what about Avifors?",
                    mode="lesson",
                    expected_standalone="Compare Disarming Charm with Avifors.",
                    expected_mode="referral",
                    materials=materials("dada", "Disarming Charm"),
                    referral=("charms", "Avifors"),
                    expected_abstained=False,
                    note="target behaviour: DADA teaches its half and refers Charms",
                ),
            ],
            note="cross-subject referral, currently expected to fail",
        ),
        _conversation(
            conversation_id="mt-cross-charms-dada",
            subject="charms",
            slice_name="cross_subject",
            turns=[
                _turn(
                    question="Tell me about Wand-Lighting Charm.",
                    mode="lesson",
                    expected_standalone="Tell me about Wand-Lighting Charm.",
                    expected_mode="lesson",
                    materials=materials("charms", "Wand-Lighting Charm"),
                ),
                _turn(
                    question="what about Expelliarmus?",
                    mode="lesson",
                    expected_standalone=("Compare Wand-Lighting Charm with Expelliarmus."),
                    expected_mode="referral",
                    materials=materials("charms", "Wand-Lighting Charm"),
                    referral=("dada", "Disarming Charm"),
                    expected_abstained=False,
                    note="target behaviour: Charms refers DADA",
                ),
            ],
            note="cross-subject referral, currently expected to fail",
        ),
        _conversation(
            conversation_id="mt-cross-potions-herbology",
            subject="potions",
            slice_name="cross_subject",
            turns=[
                _turn(
                    question="Tell me about Felix Felicis.",
                    mode="lesson",
                    expected_standalone="Tell me about Felix Felicis.",
                    expected_mode="lesson",
                    materials=materials("potions", "Felix Felicis"),
                ),
                _turn(
                    question="what about Mandrake?",
                    mode="lesson",
                    expected_standalone="Compare Felix Felicis with Mandrake.",
                    expected_mode="referral",
                    materials=materials("potions", "Felix Felicis"),
                    referral=("herbology", "Mandrake"),
                    expected_abstained=False,
                    note="target behaviour: Potions refers Herbology",
                ),
            ],
            note="cross-subject referral, currently expected to fail",
        ),
        _conversation(
            conversation_id="mt-dada-patronus",
            subject="dada",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Patronus.",
                    mode="lesson",
                    expected_standalone="Tell me about Patronus.",
                    expected_mode="lesson",
                    materials=materials("dada", "Patronus"),
                ),
                _turn(
                    question="what about Dementors?",
                    mode="lesson",
                    expected_standalone="Compare Patronus with Dementors.",
                    expected_mode="lesson",
                    materials=materials("dada", "Patronus") + materials("dada", "Dementors"),
                    groups=groups_for("dada", "Patronus", "Dementors"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-charms-summoning",
            subject="charms",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Summoning Charm.",
                    mode="lesson",
                    expected_standalone="Tell me about Summoning Charm.",
                    expected_mode="lesson",
                    materials=materials("charms", "Summoning Charm"),
                ),
                _turn(
                    question="what about Levitation Charm?",
                    mode="lesson",
                    expected_standalone="Compare Summoning Charm with Levitation Charm.",
                    expected_mode="lesson",
                    materials=materials("charms", "Summoning Charm")
                    + materials("charms", "Levitation Charm"),
                    groups=groups_for("charms", "Summoning Charm", "Levitation Charm"),
                ),
            ],
            note="same-subject comparison",
        ),
        _conversation(
            conversation_id="mt-herbology-gillyweed",
            subject="herbology",
            slice_name="same_subject_comparison",
            turns=[
                _turn(
                    question="Tell me about Gillyweed.",
                    mode="lesson",
                    expected_standalone="Tell me about Gillyweed.",
                    expected_mode="lesson",
                    materials=materials("herbology", "Gillyweed"),
                ),
                _turn(
                    question="what about Venomous Tentacula?",
                    mode="lesson",
                    expected_standalone="Compare Gillyweed with Venomous Tentacula.",
                    expected_mode="lesson",
                    materials=materials("herbology", "Gillyweed")
                    + materials("herbology", "Venomous Tentacula"),
                    groups=groups_for("herbology", "Gillyweed", "Venomous Tentacula"),
                ),
            ],
            note="same-subject comparison",
        ),
    ]
    return lesson, conversations


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    lesson, conversations = build()
    _write(REPO / "eval" / "rag" / "fixtures" / "lesson.jsonl", lesson)
    _write(REPO / "eval" / "rag" / "fixtures" / "multiturn.jsonl", conversations)
    print(f"lesson items: {len(lesson)}")
    print(f"multi-turn conversations: {len(conversations)}")
    print(f"multi-turn turns: {sum(len(c['turns']) for c in conversations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
