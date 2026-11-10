"""Write the structure-only record for one published subject pack (#128).

The pack prose lives in the gitignored `data/subjects/<subject>/` directory.
This script emits the committed record: counts, validation, topic and kind
coverage, material ids and the reproduction commands. It never copies material
text, quotes or references into git.

  uv run python scripts/record_subject_pack.py potions --version 1.0.0
  uv run python scripts/record_subject_pack.py charms --version 1.0.0 --check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.packs import (  # noqa: E402
    load_subject_pack,
    pack_fingerprint,
    validate_pack,
)
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

SCOPE_NOTES = {
    "potions": [
        "Ingredients, brewing method, potency, storage and safety are covered.",
        "Healing draughts, antidotes and poison treatment are covered.",
        "Mind and transformation potions are covered, including their limits.",
        "Dangerous brews and legendary potions are covered.",
        "Charms and DADA spellcraft are left to their own packs.",
    ],
    "transfiguration": [
        "The definition and limits of Transfiguration are covered.",
        "Object, creature and self-transfiguration are covered.",
        "Vanishing, Conjuring and switching are covered with their limits.",
        "Reversal and partial transfiguration are covered.",
        "Charms and DADA spellcraft are left to their own packs.",
    ],
    "herbology": [
        "Magical plants, greenhouses, care and safety are covered.",
        "Medicinal and dangerous plants are covered.",
        "Aquatic plants and fungi are covered.",
        "Harvesting, propagation and preservation are covered.",
        "Charms and DADA spellcraft are left to their own packs.",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--packs-path", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--record", type=Path, default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate only; do not write the record",
    )
    args = parser.parse_args()

    base = args.packs_path / args.subject
    pack = load_subject_pack(base)
    if pack.manifest.version != args.version:
        print(
            f"pack version {pack.manifest.version!r} != --version {args.version!r}",
            file=sys.stderr,
        )
        return 1
    chunks = load_chunks(args.chunks)
    index_hash = text_hash(chunks)
    result = validate_pack(pack, {chunk.id: chunk for chunk in chunks}, index_hash)
    if not result.ok:
        for error in result.errors:
            print(f"error: {error}", file=sys.stderr)
        print("refusing to write a record for an invalid pack", file=sys.stderr)
        return 1

    fingerprint = pack_fingerprint(pack)
    rows = (base / "materials.jsonl").read_text("utf-8").splitlines()
    materials = [json.loads(line) for line in rows if line.strip()]
    by_topic = Counter(material["topic"] for material in materials)
    by_kind = Counter(material["kind"] for material in materials)
    refs = sum(len(material["source_refs"]) for material in materials)
    reviewed = sum(1 for material in materials if material["review_status"] == "reviewed")

    lines = [
        f"# {args.subject.capitalize()} subject pack {pack.manifest.version}",
        "",
        f"- Date: {date.today().isoformat()}",
        f"- Subject: `{args.subject}`",
        f"- Version: `{pack.manifest.version}`",
        f"- Status: `{pack.manifest.status}`",
        f"- Fingerprint: `{fingerprint}`",
        f"- Index text hash: `{index_hash}`",
        f"- Materials: {len(materials)}",
        f"- Concepts: {len(pack.concepts)}",
        f"- Topics: {len(pack.topics)}",
        f"- Source refs: {refs}",
        f"- Reviewed materials: {reviewed}/{len(materials)}",
        "",
        "## Validation",
        "",
        "```text",
        f"validate_pack: ok={result.ok} errors={len(result.errors)} "
        f"warnings={len(result.warnings)}",
        f"materials={len(materials)} concepts={len(pack.concepts)} "
        f"topics={len(pack.topics)}",
        f"fingerprint={fingerprint}",
        "```",
        "",
        "The pack directory is gitignored. This record is structure-only and",
        "contains no corpus text; the material prose stays in the local pack and",
        "the data backup.",
        "",
        "## Topic coverage",
        "",
        "| Topic | Materials |",
        "|---|---:|",
    ]
    for topic in pack.topics:
        lines.append(f"| `{topic.topic_id}` | {by_topic.get(topic.topic_id, 0)} |")
    lines.extend(["", "## Kind mix", "", "| Kind | Materials |", "|---|---:|"])
    for kind, count in sorted(by_kind.items()):
        lines.append(f"| `{kind}` | {count} |")
    lines.extend(
        [
            "",
            "## Materials",
            "",
            "| Material id | Topic | Concept | Refs |",
            "|---|---|---|---:|",
        ]
    )
    for material in sorted(materials, key=lambda row: row["material_id"]):
        lines.append(
            f"| `{material['material_id']}` | `{material['topic']}` | "
            f"`{material['concept']}` | {len(material['source_refs'])} |"
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```text",
            f"uv run python scripts/build_seeds.py --subject {args.subject} --index-hash auto",
            f"uv run python scripts/author_subject.py {args.subject}",
            f"uv run python scripts/author_subject.py {args.subject} --mark-reviewed",
            f"uv run python scripts/author_subject.py {args.subject} --publish",
            "uv run pytest tests",
            "```",
            "",
            "A rebuild on an existing published pack needs `--force` on the draft",
            "rebuild. `--mark-reviewed` is the explicit maintainer-approval step;",
            "`--publish` refuses if any material is still draft.",
            "",
            "## Scope notes",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in SCOPE_NOTES.get(args.subject, []))
    lines.extend(
        [
            "",
        ]
    )
    record = "\n".join(lines)
    if args.check:
        print(record)
        return 0
    path = args.record or REPO / "docs" / "packs" / f"{args.subject}-{pack.manifest.version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record, encoding="utf-8")
    print(f"wrote {path}")
    print(
        f"{args.subject} {pack.manifest.version}: materials={len(materials)} "
        f"concepts={len(pack.concepts)} topics={len(pack.topics)} refs={refs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
