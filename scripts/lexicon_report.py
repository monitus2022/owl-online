"""Canon-index resolver CLI (#127): join the harvest and resolve to chunks.

Run:
    uv run python scripts/lexicon_report.py \
        --lexicon-dir data/lexicon --chunks data/chunks.jsonl
    uv run python scripts/lexicon_report.py --sample 25 \
        --lexicon-dir data/lexicon --chunks data/chunks.jsonl
    uv run python scripts/lexicon_report.py --check-only   # summarize an
                                                           # existing index

Logic lives in `app/knowledge/lexicon.py`; this file is params, IO and the
review surface. Writes `canon_index.jsonl` (gitignored): chunk ids, hashes
and spans, never book text. Every build verifies all candidates against the
corpus (id exists, text hash recomputes, span contains the phrase) and
`--sample N` prints a deterministic per-agreement review list for the
human spot-check required by the ticket.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.lexicon import (  # noqa: E402
    build_canon_index,
    canon_row,
    chunk_text_hash,
    forward_edges,
    group_chunks,
    index_chunks,
    load_entries,
    reverse_edges,
    sample_edges,
    summarize,
    verify_edges,
)
from app.schemas import Chunk  # noqa: E402


def index_chunks_from_path(path: Path) -> dict[str, Chunk]:
    return index_chunks(read_chunks(path))


def read_chunks(path: Path) -> list[Chunk]:
    return [
        Chunk.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    body = "\n".join(json.dumps(r, sort_keys=True) for r in rows)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon-dir", type=Path, default=Path("data/lexicon"))
    parser.add_argument("--chunks", type=Path, default=Path("data/chunks.jsonl"))
    parser.add_argument(
        "--out", type=Path, default=None, help="default <lexicon-dir>/canon_index.jsonl"
    )
    parser.add_argument(
        "--check-only", action="store_true", help="summarize an existing canon_index.jsonl"
    )
    parser.add_argument(
        "--sample", type=int, default=0, help="print a deterministic N-per-class review sample"
    )
    args = parser.parse_args()
    out = args.out or (args.lexicon_dir / "canon_index.jsonl")

    if args.check_only:
        rows = [
            json.loads(line)
            for line in out.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["agreement"]] = counts.get(row["agreement"], 0) + 1
        candidates = sum(len(r["candidates"]) for r in rows)
        hits = sum(r.get("total_hits", 0) for r in rows)
        print(f"canon edges: {len(rows)} | candidates retained: {candidates} | all hits: {hits}")
        print(f"by agreement: {counts}")
        return 0

    skipped: list[str] = []
    entries = load_entries(args.lexicon_dir / "entries.jsonl", skipped)
    forward = forward_edges(args.lexicon_dir / "citations.jsonl", skipped)
    reverse = reverse_edges(args.lexicon_dir / "chapter_index.jsonl")
    chunks = index_chunks_from_path(args.chunks)
    edges = build_canon_index(entries, forward, reverse, group_chunks(list(chunks.values())))

    problems = verify_edges(edges, chunks)
    write_jsonl(out, [canon_row(edge) for edge in edges])
    print(json.dumps(summarize(edges), indent=2, sort_keys=True))
    print(f"unparseable entry urls skipped: {len(skipped)}")
    print(f"integrity problems (must be 0): {len(problems)}")
    for problem in problems[:10]:
        print(f"  {problem}")

    low = [e for e in edges if e.low_precision]
    sidebar_only = [e for e in edges if "sidebar" in e.sources and "article" not in e.sources]
    print(f"low-precision queue ({len(low)}), first 20 as entry book/chapter + hit totals:")
    for e in low[:20]:
        ch = "EPI" if e.key.epilogue else e.key.chapter
        print(f"  {e.key.entry_key} b{e.key.book}c{ch} hits={e.total_hits}")
    print(f"sidebar-only queue ({len(sidebar_only)}), first 20:")
    for e in sidebar_only[:20]:
        ch = "EPI" if e.key.epilogue else e.key.chapter
        print(f"  {e.key.entry_key} b{e.key.book}c{ch}")

    if args.sample:
        for agreement, picked in sample_edges(edges, args.sample).items():
            print(f"spot-check sample ({agreement}, {len(picked)} of {args.sample} requested):")
            for e in picked:
                first = e.candidates[0] if e.candidates else None
                if first is None:
                    verdict = "no-candidate"
                else:
                    chunk = chunks.get(first.chunk_id)
                    ok = chunk is not None and first.text_hash == chunk_text_hash(chunk.text)
                    verdict = "hash-ok" if ok else "HASH-BAD"
                ch = "EPI" if e.key.epilogue else e.key.chapter
                cand = f"{first.chunk_id} {first.phrase}" if first else "-"
                print(f"  {e.key.entry_key} b{e.key.book}c{ch} | {cand} | {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
