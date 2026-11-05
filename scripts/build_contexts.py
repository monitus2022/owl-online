"""Generate contextual retrieval descriptions for each chunk.

Stage 2 of the contextual-retrieval experiment: one short, grounded context
sentence per chunk, cached by (model, chunk text). The generated file is a
drop-in replacement for data/chunks.jsonl; point --chunks at it for a run.

    uv run python scripts/build_contexts.py --limit 10
    uv run python scripts/build_contexts.py
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.index import load_chunks  # noqa: E402
from app.providers.factory import make_llm  # noqa: E402
from app.providers.openrouter import DEFAULT_MODEL  # noqa: E402
from eval.harness import CachedLlm  # noqa: E402

SYSTEM = (
    "You write short retrieval contexts for passages from a book. State what "
    "the passage is about, including named people, objects, places and events a "
    "reader might use to find it. Use only the passage and its neighbours. Do "
    "not add outside facts. Reply with one or two sentences, at most 45 words, "
    "no preamble."
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _shorten(text: str, max_chars: int) -> str:
    """Keep the first two sentences and cap the indexed context length."""
    text = " ".join(text.split())
    short = " ".join(_SENTENCE.split(text)[:2])
    if len(short) <= max_chars:
        return short
    cut = short[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:.")
    if not cut:
        cut = short[: max_chars - 1]
    return cut if cut.endswith((".", "!", "?")) else f"{cut}."


def _prompt(book: str, chapter: int, title: str, prev: str, text: str, nxt: str) -> str:
    return (
        f"Book: {book}\n"
        f"Chapter {chapter}: {title}\n"
        f"Previous passage: {prev[:300]}\n"
        f"Passage: {text}\n"
        f"Next passage: {nxt[:300]}\n\n"
        "Write the retrieval context."
    )


async def build(args: argparse.Namespace) -> int:
    default_out = REPO / "data" / "chunks_context.jsonl"
    if args.limit and args.out == default_out:
        raise SystemExit(
            "--limit needs a distinct --out; refusing to overwrite the full context file"
        )
    chunks = load_chunks(args.chunks)
    if args.limit:
        chunks = chunks[: args.limit]
    by_chapter: dict[tuple[int, int], list] = {}
    for chunk in chunks:
        key = (chunk.metadata.book_num, chunk.metadata.chapter_num)
        by_chapter.setdefault(key, []).append(chunk)

    llm = CachedLlm(
        None if args.cache_only else make_llm("openrouter", temperature=0.0),
        DEFAULT_MODEL,
        args.cache,
        variant="context",
    )
    semaphore = asyncio.Semaphore(args.concurrency)
    done = 0
    missing = 0

    async def contextualize(chunk) -> None:
        nonlocal done, missing
        siblings = by_chapter[(chunk.metadata.book_num, chunk.metadata.chapter_num)]
        index = siblings.index(chunk)
        prev = siblings[index - 1].text if index > 0 else ""
        nxt = siblings[index + 1].text if index + 1 < len(siblings) else ""
        prompt = _prompt(
            chunk.metadata.book_name,
            chunk.metadata.chapter_num,
            chunk.metadata.chapter_name,
            prev,
            chunk.text,
            nxt,
        )
        async with semaphore:
            if args.cache_only:
                context = llm.get_cached(SYSTEM, prompt)
            else:
                context = await llm.generate(SYSTEM, prompt)
        if context is None or not context.strip():
            missing += 1
        else:
            chunk.context = _shorten(context.strip(), args.max_chars)
        done += 1
        if done % 25 == 0 or done == len(chunks):
            print(f"{done}/{len(chunks)} missing={missing}", file=sys.stderr)

    await asyncio.gather(*(contextualize(chunk) for chunk in chunks))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(f"{args.out.suffix}.tmp")
    tmp.write_text(
        "\n".join(chunk.model_dump_json() for chunk in chunks) + "\n",
        encoding="utf-8",
    )
    tmp.replace(args.out)
    print(f"wrote {args.out} ({len(chunks)} chunks)")
    if missing:
        print(f"text-only fallback: {missing} chunks")
        if not args.allow_missing:
            print("rerun with --allow-missing to accept partial coverage", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate chunk contexts")
    parser.add_argument("--chunks", type=Path, default=REPO / "data" / "chunks.jsonl")
    parser.add_argument(
        "--out", type=Path, default=REPO / "data" / "chunks_context.jsonl"
    )
    parser.add_argument(
        "--cache", type=Path, default=REPO / "data" / "context_cache"
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=300)
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="use cached contexts and leave missing chunks text-only",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="accept text-only fallback for uncached chunks",
    )
    return asyncio.run(build(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
