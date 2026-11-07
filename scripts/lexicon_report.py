"""Canon-index resolver CLI (#127): join the harvest and resolve to chunks.

Run:
    uv run python scripts/lexicon_report.py \
        --lexicon-dir data/lexicon --chunks data/chunks.jsonl
    uv run python scripts/lexicon_report.py --check-only   # summarize an
                                                           # existing index

Logic lives in `app/knowledge/lexicon.py`; this file is params and IO.
Writes `canon_index.jsonl` (and prints a counts-only summary plus the review
queues). The output stays under `data/lexicon/`, gitignored: it carries chunk
ids, hashes and spans, never book text.
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
    forward_edges,
    group_chunks,
    load_entries,
    reverse_edges,
    summarize,
)
from app.schemas import Chunk  # noqa: E402


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
        print(f"canon edges: {len(rows)} | by agreement: {counts}")
        return 0

    entries = load_entries(args.lexicon_dir / "entries.jsonl")
    forward = forward_edges(args.lexicon_dir / "citations.jsonl")
    reverse = reverse_edges(args.lexicon_dir / "chapter_index.jsonl")
    chunks = read_chunks(args.chunks)
    edges = build_canon_index(entries, forward, reverse, group_chunks(chunks))

    write_jsonl(out, [canon_row(edge) for edge in edges])
    print(json.dumps(summarize(edges), indent=2, sort_keys=True))

    low_precision = [e.key.entry_key for e in edges if e.low_precision]
    sidebar_only = [
        e.key.entry_key
        for e in edges
        if "sidebar" in e.sources and "article" not in e.sources
    ]
    print(f"review queue low_precision ({len(low_precision)}), first 20: {low_precision[:20]}")
    print(f"review queue sidebar-only ({len(sidebar_only)}), first 20: {sidebar_only[:20]}")
    unresolved = [e for e in edges if not e.resolved and e.agreement != "reverse-only"]
    forward_total = summarize(edges)["by_agreement"]
    print(
        f"forward edges with no matching chunk: {len(unresolved)} of "
        f"{forward_total['forward-only'] + forward_total['both']}"
    )
    if chunks:
        ids = {c.id for c in chunks}
        bad = sum(1 for e in edges for c in e.candidates if c.chunk_id not in ids)
        print(f"candidate chunk ids missing from the corpus: {bad} (must be 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
