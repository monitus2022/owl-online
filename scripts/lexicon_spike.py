"""Spike runner for #125: harvest a hand-picked Lexicon sample locally.

Usage:
    uv run python scripts/lexicon_spike.py [--no-fetch]

Fetches the curated spell/potion entries and chapter pages below at about one
request per second (plus jitter) into the gitignored cache
`data/lexicon/pages/`, parses them with the spike parsers and writes the draft
artifacts plus a report to `data/lexicon/`. Nothing scraped is written into
git. The sample is scoped to the DADA and Charms pilot areas
(docs/lexicon-canon-index.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.ingest.lexicon.codes import (  # noqa: E402
    BUCKET_UNKNOWN,
    chapter_is_valid,
    classify,
)
from app.pipeline.ingest.lexicon.parse import (  # noqa: E402
    parse_chapter_page,
    parse_entry_page,
)

BASE = "https://www.hp-lexicon.org"
UA = "owl-online-research/0.1 (subject-pack mapping; contact: repository owner)"
DATA_DIR = REPO / "data/lexicon"

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


def page_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")


def fetch(url: str, cache_dir: Path) -> str:
    path = page_path(cache_dir, url)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    path.write_text(html, encoding="utf-8")
    time.sleep(1.0 + random.uniform(0.0, 0.4))
    return html


def write_jsonl(path: Path, rows: list[dict]) -> None:
    body = "\n".join(json.dumps(r) for r in rows)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-fetch", action="store_true", help="parse only cached pages"
    )
    args = parser.parse_args()

    cache = DATA_DIR / "pages"
    cache.mkdir(parents=True, exist_ok=True)

    entry_urls = [f"{BASE}/magic/{slug}/" for slug in SPELLS + POTIONS]
    chapter_urls = [f"{BASE}/source/the-harry-potter-novels/{c}/" for c in CHAPTERS]

    def read(url: str) -> str:
        if args.no_fetch:
            return page_path(cache, url).read_text(encoding="utf-8", errors="replace")
        return fetch(url, cache)

    entries_out, citations_out, chapters_out = [], [], []
    bucket_counts: dict[str, int] = {}
    unknown: list[tuple[str, str]] = []
    invalid_chapter: list[tuple[str, str]] = []
    fetch_fail: list[str] = []
    parse_fail: list[str] = []
    zero_citation: list[str] = []

    for url in entry_urls:
        try:
            html = read(url)
        except Exception as error:  # spike: report, keep going
            fetch_fail.append(f"{url}: {error}")
            continue
        try:
            page = parse_entry_page(html, url)
        except Exception as error:  # spike: report, keep going
            parse_fail.append(f"{url}: {error}")
            continue
        if not page.citations:
            zero_citation.append(url)
        entries_out.append(
            {
                "url": url,
                "title": page.title,
                "incantation": page.incantation,
                "magic_types": page.magic_types,
                "citations": len(page.citations),
                "related_groups": page.related_groups,
                "has_references_section": page.has_references_section,
                "unknown_tokens": page.unknown_tokens,
            }
        )
        for citation in page.citations:
            resolved = classify(citation.code)
            bucket_counts[resolved.bucket] = bucket_counts.get(resolved.bucket, 0) + 1
            if resolved.bucket == BUCKET_UNKNOWN:
                unknown.append((url, citation.code))
            elif not chapter_is_valid(resolved):
                invalid_chapter.append((url, citation.code))
            citations_out.append(
                {
                    "entry_url": url,
                    "entry_title": page.title,
                    "code": citation.code,
                    "origin": citation.origin,
                    "href": citation.href,
                    **vars(resolved),
                }
            )
        for candidate in page.unknown_tokens:
            unknown.append((url, candidate))

    reverse: set[tuple[str, int | None, str]] = set()
    for url in chapter_urls:
        try:
            page = parse_chapter_page(read(url), url)
        except Exception as error:  # spike: report, keep going
            parse_fail.append(f"PARSE-FAIL {url}: {error}")
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
        # The epilogue tab corroborates the DHE forward edge, which the
        # grammar resolves to chapter 36; key both sides the same way.
        chapter = 36 if page.is_epilogue else page.chapter_num
        for group, title, href in page.related:
            if group not in {"magic", "thing", "creature", "location", "place"}:
                continue
            if "/magic/" not in href:
                continue  # the forward sample is spell/potion only
            reverse.add((href.split("/magic/")[-1].rstrip("/"), chapter, title))

    sample_slugs = {u.split("/magic/")[-1].rstrip("/") for u in entry_urls}
    forward_pairs = {
        (c["entry_url"].split("/magic/")[-1].rstrip("/"), c.get("chapter_num"))
        for c in citations_out
        if c["bucket"] == "books" and c.get("book_num")
    }
    reverse_in_sample = {e for e in reverse if e[0] in sample_slugs}
    reverse_pairs = {(slug, chapter) for slug, chapter, _ in reverse_in_sample}
    agreements = len(forward_pairs & reverse_pairs)
    forward_only = len(forward_pairs - reverse_pairs)
    reverse_only = len(reverse_pairs - forward_pairs)

    write_jsonl(DATA_DIR / "entries.jsonl", entries_out)
    write_jsonl(DATA_DIR / "citations.jsonl", citations_out)
    write_jsonl(DATA_DIR / "chapter_index.jsonl", chapters_out)

    print(
        f"entries: {len(entries_out)}  citations: {len(citations_out)}  "
        f"chapters: {len(chapters_out)}"
    )
    print("buckets:", json.dumps(bucket_counts, sort_keys=True))
    print(f"unknown codes ({len(unknown)}):")
    for url, code in unknown[:25]:
        print(f"  {code!r} <- {url}")
    print(f"invalid chapters ({len(invalid_chapter)}):")
    for url, code in invalid_chapter[:25]:
        print(f"  {code} <- {url}")
    print(f"zero-citation entries: {len(zero_citation)}")
    for url in zero_citation[:25]:
        print(f"  {url}")
    print(f"fetch failures: {len(fetch_fail)}  parse failures: {len(parse_fail)}")
    for line in (fetch_fail + parse_fail)[:10]:
        print(f"  {line}")
    print(
        f"reverse edges in sample chapters: {len(reverse_in_sample)}  "
        f"both: {agreements}  forward-only: {forward_only}  reverse-only: {reverse_only}"
    )


if __name__ == "__main__":
    main()
