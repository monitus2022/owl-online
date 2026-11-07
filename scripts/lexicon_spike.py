"""Spike runner for #125: harvest a hand-picked Lexicon sample locally.

Usage:
    uv run python scripts/lexicon_spike.py [--no-fetch]

Fetches the curated spell/potion entries and chapter pages below at one
request per second into the gitignored cache `data/lexicon/pages/`, parses
them with the spike parsers and writes the draft artifacts plus a report to
`data/lexicon/`. Nothing scraped is written into git. The sample is scoped to
the DADA and Charms pilot areas (docs/lexicon-canon-index.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.ingest.lexicon.codes import BUCKET_UNKNOWN, classify  # noqa: E402
from app.pipeline.ingest.lexicon.parse import (  # noqa: E402
    parse_chapter_page,
    parse_entry_page,
)

BASE = "https://www.hp-lexicon.org"
UA = "owl-online-research/0.1 (subject-pack mapping; contact: repository owner)"

SPELLS = [
    "summoning-charm", "disarming-charm", "unlocking-charm", "levitation-charm",
    "patronus-charm", "corporeal-patronus", "boggart-banishing-spell",
    "stunning-spell", "cruciatus-curse", "imperius-curse", "killing-curse",
    "sectumsempra", "sectumsempra-countercurse", "vanishing-spell",
    "shrinking-charm", "engorgement-charm", "levicorpus", "anapneo",
    "impervius", "confundus-charm", "cushioning-charm", "cheering-charm",
    "disillusionment-charm", "banishing-charm", "freezing-charm",
    "anti-jinx", "countercurse", "protego-diabolica", "finite",
    "animagus-transfiguration", "canary-transfiguration-hex",
]
POTIONS = [
    "wolfsbane-potion", "polyjuice-potion", "felix-felicis", "veritaserum",
    "amortentia", "pepperup-potion", "mandrake-draught", "boil-cure-potion",
    "blood-replenishing-potion", "wit-sharpening-potion", "wiggenweld-potion",
    "ageing-potion", "wideye-or-awakening-potion", "sleeping-draughtpotion",
    "potion-for-dreamless-sleep", "living-death-draught-of",
    "antidote-to-common-poisons", "calming-draught", "deflating-draught",
    "love-potion", "laughing-potion", "wound-cleaning-potion",
    "shrinking-solution-shrinking-potion", "bruise-healing-paste",
]
CHAPTERS = [
    "ps/ps6", "pa/pa8", "pa/pa15", "gf/gf6", "gf/gf20", "gf/gf34",
    "op/op18", "op/op29", "op/op35", "hbp/hbp8", "hbp/hbp26", "dh/dh10",
    "dh/dh36", "dh/dhe",
]

_ENTRY_SLUG_RE = re.compile(r"/magic/([a-z0-9-]+)/?")


def page_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")


def fetch(url: str, cache_dir: Path, sleep: float = 1.0) -> str:
    path = page_path(cache_dir, url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    time.sleep(sleep)
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-fetch", action="store_true", help="parse only cached pages"
    )
    args = parser.parse_args()

    root = Path("data/lexicon")
    cache = root / "pages"
    cache.mkdir(parents=True, exist_ok=True)

    entry_urls = [f"{BASE}/magic/{slug}/" for slug in SPELLS + POTIONS]
    chapter_urls = [f"{BASE}/source/the-harry-potter-novels/{c}/" for c in CHAPTERS]

    entries_out, citations_out, chapters_out = [], [], []
    bucket_counts: dict[str, int] = {}
    unknown: list[tuple[str, str]] = []
    no_refs: list[str] = []
    fetch_html = (
        (lambda url: page_path(cache, url).read_text(encoding="utf-8", errors="replace"))
        if args.no_fetch
        else (lambda url: fetch(url, cache))
    )

    for url in entry_urls:
        try:
            html = fetch_html(url)
        except Exception as error:  # noqa: BLE001 - the spike reports loudly
            no_refs.append(f"{url} FETCH-FAIL {error}")
            continue
        page = parse_entry_page(html, url)
        if not page.citations:
            no_refs.append(url)
        entries_out.append(
            {
                "url": url,
                "title": page.title,
                "incantation": page.incantation,
                "magic_types": page.magic_types,
                "citations": len(page.citations),
                "related_groups": page.related_groups,
                "has_references_section": page.has_references_section,
            }
        )
        for citation in page.citations:
            resolved = classify(citation.code)
            bucket_counts[resolved.bucket] = bucket_counts.get(resolved.bucket, 0) + 1
            if resolved.bucket == BUCKET_UNKNOWN:
                unknown.append((url, citation.code))
            citations_out.append(
                {
                    "entry_url": url,
                    "entry_title": page.title,
                    "code": citation.code,
                    "origin": citation.origin,
                    "bullet": citation.bullet,
                    "href": citation.href,
                    **vars(resolved),
                }
            )
        for candidate in page.bare_code_candidates:
            unknown.append((url, candidate))

    reverse: set[tuple[str, int | None, str]] = set()
    for url in chapter_urls:
        try:
            html = fetch_html(url)
            page = parse_chapter_page(html, url)
        except Exception as error:  # noqa: BLE001
            no_refs.append(f"{url} PARSE-FAIL {error}")
            continue
        chapters_out.append(
            {
                "url": url,
                "code": page.code,
                "chapter_num": page.chapter_num,
                "is_epilogue": page.is_epilogue,
                "abbreviation": page.abbreviation,
                "canonicity": page.canonicity,
                "related": page.related,
            }
        )
        for group, title, href in page.related:
            if group in {"character", "essay", "quote", "trivia"}:
                continue
            slug = href.split("/magic/")[-1].rstrip("/") if "/magic/" in href else href
            reverse.add((slug, -1 if page.is_epilogue else page.chapter_num, title))

    forward_slugs = {
        (c["entry_url"].split("/magic/")[-1].rstrip("/"), c.get("chapter_num"))
        for c in citations_out
        if c["bucket"] == "books" and c.get("book_num")
    }
    agreements = sum(1 for slug, chapter, _ in reverse if (slug, chapter) in forward_slugs)

    (root / "entries.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries_out) + "\n", encoding="utf-8"
    )
    (root / "citations.jsonl").write_text(
        "\n".join(json.dumps(c) for c in citations_out) + "\n", encoding="utf-8"
    )
    (root / "chapter_index.jsonl").write_text(
        "\n".join(json.dumps(c) for c in chapters_out) + "\n", encoding="utf-8"
    )

    print(
        f"entries: {len(entries_out)}  citations: {len(citations_out)}  "
        f"chapters: {len(chapters_out)}"
    )
    print("buckets:", json.dumps(bucket_counts, sort_keys=True))
    print(f"unknown codes ({len(unknown)}):")
    for url, code in unknown[:25]:
        print(f"  {code!r} <- {url}")
    print(f"no citations ({len(no_refs)}):")
    for url in no_refs[:25]:
        print(f"  {url}")
    print(f"reverse edges: {len(reverse)}  agreeing with forward: {agreements}")


if __name__ == "__main__":
    main()
