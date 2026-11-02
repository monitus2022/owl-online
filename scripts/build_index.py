"""One-time index build + smoke query: thin CLI over pipeline composition.

Run: uv run python scripts/build_index.py
Logic lives in app.pipeline (index building, retrieval composition); this file
is params, progress printing and smoke-query output only.

Keys: data/index/chroma (gitignored). Embeds the whole corpus on first run
(~26 min on 0.6b); later runs reuse the persisted collection unless the chunk
count or embedder slug changed. A/B another model with:
  uv run python scripts/build_index.py --model qwen3-embedding:4b --index data/index/chroma-4b
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.retrieve import compose_retriever  # noqa: E402
from app.providers.factory import make_embedder  # noqa: E402

_BATCH_PRINT_STRIDE = 10


def _progress(done: int, total: int) -> None:
    if done % (_BATCH_PRINT_STRIDE * 128) == 0 or done == total:
        print(f"embedded {done}/{total}", flush=True)


def _print_hits(hits, query: str) -> None:
    print(f"smoke query: {query!r}")
    for c in hits:
        print(
            f"  {c.score:.4f}  {c.id}  "
            f"b{c.metadata.book_num} c{c.metadata.chapter_num} {c.metadata.chapter_name}"
        )
        print(f"    {c.text[:100]}...")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the retrieval index from chunks JSONL")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument("--index", type=Path, default=REPO / "data" / "index" / "chroma")
    parser.add_argument("--model", default="qwen3-embedding:0.6b")
    parser.add_argument("--query", default="Where do the Dursleys live?")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    async def run() -> int:
        setup = await compose_retriever(
            args.chunks, args.index, make_embedder("local", model=args.model), progress=_progress
        )
        state = "rebuilt" if setup.rebuilt else "reused"
        print(f"chunks: {setup.chunks} | embedder: {setup.embedder} | dims: {setup.dims} | {state}")
        hits = await setup.retriever.retrieve(args.query, args.top_k)
        _print_hits(hits, args.query)
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())