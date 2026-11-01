"""One-time corpus ingestion CLI: PDF -> validated chunks JSONL.

Run: uv run python scripts/ingest_corpus.py
Output: data/chunks.jsonl (local only).
Logic lives in app/pipeline/ingest/ingest_corpus.py; this file is params only.
"""

import argparse
import sys
from pathlib import Path

# A direct file run puts scripts/ (not the repo root) on sys.path, so `app`
# imports fail. Inserting the repo root makes both invocation styles work:
#   uv run python scripts/ingest_corpus.py
#   uv run python -m scripts.ingest_corpus   (from the repo root)
REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.ingest.ingest_corpus import ingest_corpus  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest the corpus into chunks JSONL")
    parser.add_argument("--pdf", type=Path, default=REPO / "data" / "harrypotter.pdf")
    parser.add_argument("--cache", type=Path, default=REPO / "data" / "corpus_pages.txt")
    parser.add_argument("--out", type=Path, default=REPO / "data" / "chunks.jsonl")
    args = parser.parse_args()

    summary = ingest_corpus(args.pdf, args.cache, args.out)
    print(f"pages: {summary.pages}")
    print(f"books: {summary.books}, chapters: {summary.chapters}")
    print(f"chunks: {summary.total_chunks} -> {args.out}")
    print(f"per book: {summary.per_book}")
    print(
        f"char sizes: min={summary.min_size} median={summary.median_size} max={summary.max_size}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())