"""Render a bank review sheet from a built exam bank and its source pack.

The review sheet is local and gitignored. It lists every prompt, key, golden
answer, rubric, cited material and evidence quote so the maintainer can review
the bank without opening the JSONL.

  uv run python scripts/render_bank_review.py potions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.exam.bank import load_exam_bank  # noqa: E402
from app.knowledge.packs import load_subject_pack  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("subject")
    parser.add_argument("--exams-path", type=Path, default=REPO / "data" / "exams")
    parser.add_argument("--subjects-path", type=Path, default=REPO / "data" / "subjects")
    args = parser.parse_args()

    bank = load_exam_bank(args.exams_path / args.subject)
    pack = load_subject_pack(args.subjects_path / args.subject)
    materials = {material.material_id: material for material in pack.materials}

    lines = [
        f"# {args.subject.capitalize()} exam bank {bank.manifest.version} review",
        "",
        f"- Bank status: `{bank.manifest.status}`",
        f"- Pack: `{bank.manifest.pack_version}` / `{bank.manifest.pack_fingerprint}`",
        f"- Items: {len(bank.items)}",
        "- Scope: concept-only; no character, plot, exam or lesson questions",
        "",
        "Each item lists its prompt, key, rationale, cited material text and",
        "evidence. The question and key use only subject concepts; evidence",
        "quotes may come from a scene.",
        "",
    ]
    for item in bank.items:
        material = materials[item.material_id]
        lines.append(f"## {item.item_id} ({item.kind}, {item.topic})")
        lines.append("")
        lines.append(item.prompt)
        lines.append("")
        if item.kind == "mcq":
            for option in item.options:
                suffix = " <- correct" if option.option_id == item.correct_option_id else ""
                lines.append(f"- {option.option_id}. {option.text}{suffix}")
            lines.append("")
            lines.append(f"Rationale: {item.rationale}")
        else:
            lines.append(f"Golden answer: {item.model_answer}")
            lines.append("")
            lines.append("Required points: " + "; ".join(item.required_points))
            lines.append("")
            lines.append(
                "Rubric: "
                + "; ".join(
                    f"{criterion.criterion_id} {criterion.max_marks} "
                    f"({criterion.description})"
                    for criterion in item.rubric
                )
            )
        lines.append("")
        lines.append(f"Material `{item.material_id}`: {material.text}")
        lines.append("")
        lines.append("Evidence:")
        for ref in item.source_refs:
            lines.append(f"- [{ref.chunk_id}] {ref.quote}")
        lines.append("")

    path = (
        args.exams_path
        / args.subject
        / f"{args.subject.upper()}_BANK_REVIEW.md"
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
