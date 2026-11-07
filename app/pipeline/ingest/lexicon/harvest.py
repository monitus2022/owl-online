"""Harvest orchestration for the Lexicon canon index (#126).

Runs the work queue through the Fetcher and the spike parsers, writing the
draft artifacts to `data/lexicon/` (all gitignored):

- entries.jsonl, citations.jsonl, chapter_index.jsonl (same shapes as the
  #125 spike, plus slug/family fields);
- fetch_index.jsonl: url, path, fetched_at, response sha256 (etiquette rule);
- harvest_failures.jsonl: url, stage, reason - every failure names its page.

No scraped prose is returned or printed; the summary carries counts only.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict
from pathlib import Path

from app.pipeline.ingest.lexicon.codes import BUCKET_BOOKS, chapter_is_valid
from app.pipeline.ingest.lexicon.discovery import QueueItem
from app.pipeline.ingest.lexicon.fetch import Fetcher
from app.pipeline.ingest.lexicon.parse import parse_chapter_page, parse_entry_page


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    body = "\n".join(json.dumps(r) for r in rows)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


def harvest(
    queue: list[QueueItem],
    out_dir: Path,
    fetcher: Fetcher,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Harvest the queue; returns the aggregate summary (counts only)."""
    entries: list[dict] = []
    citations: list[dict] = []
    chapters: list[dict] = []
    fetch_meta: list[dict] = []
    failures: list[dict] = []
    unknown_counts: dict[str, int] = {}
    invalid_chapter: list[dict] = []
    buckets: dict[str, int] = {}
    zero_citation = 0
    sidebar_missing: list[str] = []

    for index, item in enumerate(queue):
        if progress:
            progress(index + 1, len(queue))
        try:
            record, html = fetcher.fetch(item.url)
        except Exception as error:  # transport boundary: name the page, keep going
            failures.append({"url": item.url, "stage": "fetch", "reason": str(error)})
            continue
        fetch_meta.append(asdict(record))
        try:
            if item.kind == "chapter":
                page = parse_chapter_page(html, item.url)
                chapters.append(
                    {
                        "url": item.url,
                        "code": page.code,
                        "chapter_num": page.chapter_num,
                        "is_epilogue": page.is_epilogue,
                        "abbreviation": page.abbreviation,
                        "canonicity": page.canonicity,
                        "related": page.related,
                    }
                )
                continue
            page = parse_entry_page(html, item.url)
        except Exception as error:  # parser boundary: name the page, keep going
            failures.append({"url": item.url, "stage": "parse", "reason": str(error)})
            continue
        if not page.citations:
            zero_citation += 1
        if item.kind == "entry" and not page.sidebar_scanned:
            sidebar_missing.append(item.url)
        entries.append(
            {
                "url": item.url,
                "slug": item.url.rstrip("/").rsplit("/", 1)[-1],
                "family": item.family,
                "title": page.title,
                "incantation": page.incantation,
                "magic_types": page.magic_types,
                "citations": len(page.citations),
                "related_groups": page.related_groups,
                "has_references_section": page.has_references_section,
                "sidebar_scanned": page.sidebar_scanned,
                "unknown_tokens": page.unknown_tokens,
            }
        )
        for citation in page.citations:
            resolved = citation.resolved
            buckets[resolved.bucket] = buckets.get(resolved.bucket, 0) + 1
            valid = resolved.bucket != BUCKET_BOOKS or chapter_is_valid(resolved)
            if not valid:
                # A books code the corpus cannot hold (a site-broken href like
                # dh117): recorded, flagged, and queued - never resolved.
                invalid_chapter.append({"entry_url": item.url, "code": citation.code})
            citations.append(
                {
                    "entry_url": item.url,
                    "entry_title": page.title,
                    "family": item.family,
                    "code": citation.code,
                    "origin": citation.origin,
                    "href": citation.href,
                    "valid_chapter": valid,
                    **vars(resolved),
                }
            )
        for token in page.unknown_tokens:
            unknown_counts[token] = unknown_counts.get(token, 0) + 1

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "entries.jsonl", entries)
    write_jsonl(out_dir / "citations.jsonl", citations)
    write_jsonl(out_dir / "chapter_index.jsonl", chapters)
    write_jsonl(out_dir / "fetch_index.jsonl", fetch_meta)
    write_jsonl(out_dir / "harvest_failures.jsonl", failures)
    write_jsonl(out_dir / "invalid_chapters.jsonl", invalid_chapter)
    write_jsonl(out_dir / "sidebar_missing.jsonl", [{"url": u} for u in sidebar_missing])

    return {
        "queued": len(queue),
        "entries": len(entries),
        "chapters": len(chapters),
        "citations": len(citations),
        "buckets": buckets,
        "zero_citation_entries": zero_citation,
        "invalid_chapter_edges": len(invalid_chapter),
        "sidebar_missing": len(sidebar_missing),
        "unknown_codes": len(unknown_counts),
        "unknown_top": sorted(unknown_counts.items(), key=lambda kv: -kv[1])[:20],
        "failures": len(failures),
    }
