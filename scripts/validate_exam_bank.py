"""Validate a subject exam bank against its pack and the current corpus (#189).

Run:
    uv run python scripts/validate_exam_bank.py --subject dada

Reads `data/exams/<subject>/manifest.toml` and `bank.jsonl`, validates every
item against the published pack, recomputes source-ref hashes against
`data/chunks.jsonl`, checks duplicate prompts and prints the coverage summary.
Exits non-zero on any error. No exam content is generated here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.exam.bank import load_exam_bank, structure_record, validate_bank  # noqa: E402
from app.knowledge.packs import load_subject_pack  # noqa: E402
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="dada")
    parser.add_argument("--exams-path", type=Path, default=REPO / "data" / "exams")
    parser.add_argument("--subjects-path", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--record", type=Path, default=None)
    args = parser.parse_args()

    pack = load_subject_pack(args.subjects_path / args.subject)
    chunks = load_chunks(args.chunks)
    index_hash = text_hash(chunks)
    try:
        bank = load_exam_bank(args.exams_path / args.subject)
    except ValueError as error:
        print(f"error: {error}")
        return 1
    validation = validate_bank(
        bank,
        pack,
        {chunk.id: chunk for chunk in chunks},
        index_hash,
    )

    counts = bank.counts()
    print(
        f"bank {bank.manifest.subject} {bank.manifest.version} "
        f"status={bank.manifest.status} mcq={counts['mcq']} "
        f"short_answer={counts['short_answer']}"
    )
    print(
        f"pack {pack.manifest.subject} {pack.manifest.version} "
        f"fingerprint={bank.manifest.pack_fingerprint} index={index_hash}"
    )
    print(f"coverage: {len(validation.coverage.per_topic)} topics, "
          f"{len(validation.coverage.per_concept)} concepts")
    for topic, kind_counts in sorted(validation.coverage.per_topic_kind.items()):
        print(
            f"  {topic}: mcq={kind_counts.get('mcq', 0)} "
            f"short={kind_counts.get('short_answer', 0)}"
        )
    print(f"answer positions: {dict(sorted(validation.coverage.answer_positions.items()))}")
    for warning in validation.warnings:
        print(f"warning: {warning}")
    for error in validation.errors:
        print(f"error: {error}")
    print(f"validate_bank: ok={validation.ok} errors={len(validation.errors)} "
          f"warnings={len(validation.warnings)}")
    if args.record and validation.ok:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(structure_record(bank, validation), encoding="utf-8")
        print(f"wrote record {args.record}")
    elif args.record:
        print("not writing record: validation failed")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
