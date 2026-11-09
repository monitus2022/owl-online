"""Coverage and duplicate-risk report for an exam-bank source pack (#188).

Reads a published subject pack and the canon-index seed queue, then prints the
matrix the bank blueprint needs:

- topic, concept and material coverage;
- per-topic capacity for a 25 MCQ + 25 short-answer bank;
- a cheap token-Jaccard duplicate-risk read over material texts;
- practitioner context already present in the reviewed materials;
- unused seed candidates for a possible later pack top-up.

Structure only: the report prints ids, titles, counts and word counts, never
material prose or book text. Run:

    uv run python scripts/bank_coverage.py --subject dada

The blueprint curates its duplicate pairs, practitioner table and gap table
from this output. The counts and the topic, concept and material matrices are
reproduced directly. The go/top-up decision is a human call.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.packs import (  # noqa: E402
    SubjectPack,
    load_subject_pack,
    pack_fingerprint,
    validate_pack,
)
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

STOPWORDS = frozenset(
    "the a an and or but if then than that this these those of to in on for with by from "
    "as at is are was were be been being it its their his her they he she we you i not no "
    "so very can could would should may might will just also into over under about after "
    "before more most other some such only own same too now don s t".split()
)

PRACTITIONERS = (
    "Moody",
    "Lupin",
    "Snape",
    "Dumbledore",
    "Harry",
    "Hermione",
    "Neville",
    "Sirius",
    "Umbridge",
    "Lockhart",
    "Hagrid",
    "Flitwick",
    "McGonagall",
)

GAP_BLOCKLIST = (
    "transfiguration",
    "divination",
    "charms",
    "apparition",
    "owl",
    "house-elf",
    "quidditch",
    "muggle",
    "great hall",
    "defence against the dark arts",
    "dark arts",
    "curses",
    "hexes",
    "jinxes",
    "love",
    "music",
    "remorse",
    "dark magic",
    "house-elf",
    "house-elves",
    "beetle",
    "frog",
    "toad",
)


def content_tokens(text: str) -> set[str]:
    """Lower-case content words for the duplicate-risk proxy."""
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if len(word) > 2 and word not in STOPWORDS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def material_rows(pack: SubjectPack) -> list[dict]:
    return [
        {
            "id": material.material_id,
            "topic": material.topic,
            "concept": material.concept,
            "kind": material.kind,
            "words": len(material.text.split()),
            "refs": len(material.source_refs),
        }
        for material in pack.materials
    ]


def topic_rows(pack: SubjectPack, rows: list[dict]) -> list[dict]:
    topic_titles = {topic.topic_id: topic.title for topic in pack.topics}
    total_materials = len(rows)
    output = []
    for topic_id, title in topic_titles.items():
        subset = [row for row in rows if row["topic"] == topic_id]
        output.append(
            {
                "topic": topic_id,
                "title": title,
                "materials": len(subset),
                "concepts": len({row["concept"] for row in subset}),
                "words": sum(row["words"] for row in subset),
                "refs": sum(row["refs"] for row in subset),
                "share": len(subset) / total_materials if total_materials else 0.0,
                "mcq_capacity": len(subset),
                "short_capacity": len(subset),
            }
        )
    return output


def concept_rows(pack: SubjectPack, rows: list[dict]) -> list[dict]:
    output = []
    for concept in sorted(pack.concepts, key=lambda item: item.concept_id):
        subset = [row for row in rows if row["concept"] == concept.concept_id]
        output.append(
            {
                "concept": concept.concept_id,
                "kind": concept.kind,
                "title": concept.title,
                "materials": len(subset),
                "refs": sum(row["refs"] for row in subset),
                "words": sum(row["words"] for row in subset),
            }
        )
    return output


def similarity_rows(pack: SubjectPack, limit: int = 10) -> list[dict]:
    tokens = {
        material.material_id: content_tokens(material.text)
        for material in pack.materials
    }
    rows = []
    for left, right in itertools.combinations(pack.materials, 2):
        left_id, right_id = left.material_id, right.material_id
        rows.append(
            {
                "left": left_id,
                "right": right_id,
                "jaccard": jaccard(tokens[left_id], tokens[right_id]),
            }
        )
    rows.sort(key=lambda row: (-row["jaccard"], row["left"], row["right"]))
    return rows[:limit]


def similarity_stats(pack: SubjectPack) -> dict:
    """Maximum and median pairwise Jaccard over all material pairs."""
    tokens = {
        material.material_id: content_tokens(material.text)
        for material in pack.materials
    }
    values = [
        jaccard(tokens[left.material_id], tokens[right.material_id])
        for left, right in itertools.combinations(pack.materials, 2)
    ]
    if not values:
        return {"max": 0.0, "median": 0.0}
    values.sort()
    middle = len(values) // 2
    median = values[middle]
    if len(values) % 2 == 0:
        median = (values[middle - 1] + values[middle]) / 2
    return {"max": values[-1], "median": median}


def practitioner_rows(pack: SubjectPack) -> list[dict]:
    output = []
    for name in PRACTITIONERS:
        material_ids = [
            material.material_id
            for material in pack.materials
            if name.lower() in material.text.lower()
        ]
        output.append({"name": name, "materials": material_ids})
    return output


def gap_rows(pack: SubjectPack, seeds_path: Path, limit: int = 20) -> list[dict]:
    """Unused seed candidates, with a flag for names already in material text."""
    if not seeds_path.exists():
        return []
    pack_ids = pack.concept_ids()
    concept_names = {concept.title.lower() for concept in pack.concepts}
    for concept in pack.concepts:
        concept_names.update(alias.lower() for alias in concept.aliases)
    material_text = " ".join(material.text.lower() for material in pack.materials)
    candidates: dict[str, dict] = {}
    for line in seeds_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        seed = json.loads(line)
        if seed.get("subject") not in (None, pack.manifest.subject):
            continue
        concept_id = str(seed.get("concept_id", ""))
        title = str(seed.get("title", ""))
        lowered = title.lower()
        if not concept_id or concept_id in pack_ids:
            continue
        if lowered in concept_names:
            continue
        if seed.get("kind") not in {"creature", "spell", "event"}:
            continue
        if any(blocked in lowered for blocked in GAP_BLOCKLIST):
            continue
        if concept_id in candidates:
            continue
        candidates[concept_id] = {
            "concept": concept_id,
            "kind": seed.get("kind", ""),
            "title": title,
            "refs": len(seed.get("source_refs", ())),
            "basis": seed.get("basis", ""),
            "mentioned_in_material": lowered in material_text,
        }
    rows = list(candidates.values())
    rows.sort(key=lambda row: (-row["refs"], row["title"]))
    return rows[:limit]


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        cells = [str(value).replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def render(
    pack: SubjectPack,
    *,
    validation_errors: list[str],
    validation_warnings: list[str],
    index_hash: str,
    materials: list[dict],
    topics: list[dict],
    concepts: list[dict],
    similarities: list[dict],
    similarity_summary: dict,
    practitioners: list[dict],
    gaps: list[dict],
) -> str:
    lines: list[str] = []
    lines.append(f"# Pack coverage: {pack.manifest.subject} {pack.manifest.version}")
    lines.append("")
    lines.append(f"- Fingerprint: `{pack_fingerprint(pack)}`")
    lines.append(f"- Index text hash: `{index_hash}`")
    lines.append(f"- Materials: {len(pack.materials)}")
    lines.append(f"- Concepts: {len(pack.concepts)}")
    lines.append(f"- Topics: {len(pack.topics)}")
    lines.append(f"- Validation errors: {len(validation_errors)}")
    lines.append(f"- Validation warnings: {len(validation_warnings)}")
    lines.append("")

    lines.append("## Topics")
    lines.append("")
    lines.extend(
        _table(
            [
                "Topic",
                "Title",
                "Materials",
                "Concepts",
                "Words",
                "Refs",
                "Share",
                "MCQ capacity",
                "Short capacity",
            ],
            [
                [
                    row["topic"],
                    row["title"],
                    row["materials"],
                    row["concepts"],
                    row["words"],
                    row["refs"],
                    f"{row['share']:.0%}",
                    row["mcq_capacity"],
                    row["short_capacity"],
                ]
                for row in topics
            ],
        )
    )
    lines.append("")

    lines.append("## Concepts")
    lines.append("")
    lines.extend(
        _table(
            ["Concept", "Kind", "Title", "Materials", "Refs", "Words"],
            [
                [
                    row["concept"],
                    row["kind"],
                    row["title"],
                    row["materials"],
                    row["refs"],
                    row["words"],
                ]
                for row in concepts
            ],
        )
    )
    lines.append("")

    lines.append("## Materials")
    lines.append("")
    lines.extend(
        _table(
            ["Material", "Topic", "Concept", "Kind", "Words", "Refs"],
            [
                [
                    row["id"],
                    row["topic"],
                    row["concept"],
                    row["kind"],
                    row["words"],
                    row["refs"],
                ]
                for row in materials
            ],
        )
    )
    lines.append("")

    lines.append("## Duplicate-risk proxy")
    lines.append("")
    lines.append(
        "Token Jaccard over material texts, stopwords removed. This is a cheap "
        "read, not a question-stem duplicate check."
    )
    lines.append("")
    lines.append(f"- Maximum: {similarity_summary['max']:.3f}")
    lines.append(f"- Median: {similarity_summary['median']:.3f}")
    lines.append("")
    lines.extend(
        _table(
            ["Material A", "Material B", "Jaccard"],
            [
                [row["left"], row["right"], f"{row['jaccard']:.3f}"]
                for row in similarities
            ],
        )
    )
    lines.append("")

    lines.append("## Practitioner context")
    lines.append("")
    lines.append(
        "Reviewed materials that mention each practitioner. This is evidence "
        "that practitioner questions can be grounded without a separate "
        "practitioner material."
    )
    lines.append("")
    lines.extend(
        _table(
            ["Practitioner", "Material ids"],
            [
                [row["name"], ", ".join(f"`{value}`" for value in row["materials"]) or "-"]
                for row in practitioners
            ],
        )
    )
    lines.append("")

    lines.append("## Unused seed candidates")
    lines.append("")
    lines.append(
        "Seeds outside the published pack, ranked by source-ref count. A title "
        "already named inside a material is marked as mentioned, not unused."
    )
    lines.append("")
    lines.extend(
        _table(
            ["Concept", "Kind", "Title", "Refs", "Basis", "Mentioned"],
            [
                [
                    row["concept"],
                    row["kind"],
                    row["title"],
                    row["refs"],
                    row["basis"],
                    "yes" if row["mentioned_in_material"] else "no",
                ]
                for row in gaps
            ],
        )
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="dada")
    parser.add_argument("--subjects-path", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--seeds", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    pack_dir = args.subjects_path / args.subject
    pack = load_subject_pack(pack_dir)
    chunks = load_chunks(args.chunks)
    index_hash = text_hash(chunks)
    validation = validate_pack(pack, {chunk.id: chunk for chunk in chunks}, index_hash)

    materials = material_rows(pack)
    topics = topic_rows(pack, materials)
    concepts = concept_rows(pack, materials)
    similarities = similarity_rows(pack)
    similarity_summary = similarity_stats(pack)
    practitioners = practitioner_rows(pack)
    seeds = args.seeds or (args.subjects_path / args.subject / "seeds.jsonl")
    gaps = gap_rows(pack, seeds)

    body = render(
        pack,
        validation_errors=validation.errors,
        validation_warnings=validation.warnings,
        index_hash=index_hash,
        materials=materials,
        topics=topics,
        concepts=concepts,
        similarities=similarities,
        similarity_summary=similarity_summary,
        practitioners=practitioners,
        gaps=gaps,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(body + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(body)

    print(f"pack status: {pack.manifest.status}")
    for warning in validation.warnings:
        print(f"warning: {warning}")
    for error in validation.errors:
        print(f"error: {error}")
    if pack.manifest.status != "published":
        print("warning: pack is not published; do not base a bank decision on it")
    return 1 if validation.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
