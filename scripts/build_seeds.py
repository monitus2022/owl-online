"""Build concept seeds for one subject: canon index x approved lesson table.

Thin wrapper over `app.knowledge.seeding` (#128). Seeds and queues are
gitignored local artifacts under `data/subjects/<subject>/`; authoring
materials and publishing a pack is separate, reviewed work.

  uv run python scripts/build_seeds.py --subject dada
  uv run python scripts/build_seeds.py --subject charms --index-hash auto
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.seeding import build_seeds, write_bundle  # noqa: E402
from app.pipeline.index.builder import load_chunks  # noqa: E402


def _index_hash(chunks_path: Path) -> str:
    # the same corpus hash the index builder records in the manifest
    from app.pipeline.index import builder

    return builder._text_hash(load_chunks(chunks_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--lexicon-dir", type=Path, default=REPO / "data" / "lexicon")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--lesson", type=Path, default=None,
                        help="default config/lessons/<subject>.jsonl")
    parser.add_argument("--index-hash", default="auto",
                        help="'auto' recomputes from --chunks; else literal")
    parser.add_argument("--out", type=Path, default=None,
                        help="default data/subjects/<subject>/")
    args = parser.parse_args()

    lesson = args.lesson or REPO / "config" / "lessons" / f"{args.subject}.jsonl"
    if not lesson.exists():
        print(f"no lesson table for {args.subject!r} at {lesson}", file=sys.stderr)
        return 1
    index_hash = (args.index_hash if args.index_hash != "auto"
                  else _index_hash(args.chunks))
    bundle = build_seeds(
        args.subject,
        args.lexicon_dir / "canon_index.jsonl",
        lesson,
        args.lexicon_dir / "entries.jsonl",
        args.lexicon_dir / "fetch_index.jsonl",
        index_text_hash=index_hash,
    )
    path = write_bundle(bundle, args.out or REPO / "data" / "subjects" / args.subject)
    stats = bundle.stats()
    stats["index_text_hash"] = index_hash
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
