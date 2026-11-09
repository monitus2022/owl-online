"""Import a validated exam bank into the SQLite serving store (#189).

Run:
    uv run python scripts/import_exam_bank.py --subject dada

The importer runs the same pack/corpus validation as the validator first. A
draft bank is refused unless `--allow-draft` is passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.exam.bank import load_exam_bank, validate_bank  # noqa: E402
from app.knowledge.packs import load_subject_pack  # noqa: E402
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402
from app.storage.exam_store import ExamStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="dada")
    parser.add_argument("--exams-path", type=Path, default=REPO / "data" / "exams")
    parser.add_argument("--subjects-path", type=Path, default=REPO / "data" / "subjects")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--db", type=Path, default=REPO / "data" / "exams" / "exams.db")
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    pack = load_subject_pack(args.subjects_path / args.subject)
    chunks = load_chunks(args.chunks)
    index_hash = text_hash(chunks)
    try:
        bank = load_exam_bank(args.exams_path / args.subject)
    except ValueError as error:
        print(f"error: {error}")
        return 1
    validation = validate_bank(bank, pack, {chunk.id: chunk for chunk in chunks}, index_hash)
    if not validation.ok:
        for error in validation.errors:
            print(f"error: {error}")
        print("refusing to import an invalid bank")
        return 1
    if bank.manifest.status == "draft" and not args.allow_draft:
        print("refusing to import a draft bank; pass --allow-draft to override")
        return 1

    with ExamStore(args.db) as store:
        try:
            store.replace_bank(bank, force=args.force)
        except ValueError as error:
            print(f"error: {error}")
            return 1
        counts = store.counts(args.subject, bank.manifest.version)
        print(
            f"imported {args.subject} {bank.manifest.version} into {args.db}: "
            f"mcq={counts['mcq']} short_answer={counts['short_answer']}"
        )
        print(f"versions: {store.versions(args.subject)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
