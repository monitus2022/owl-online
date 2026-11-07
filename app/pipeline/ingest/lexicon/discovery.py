"""Sitemap discovery for the Lexicon harvest (#126).

The site ships Yoast sitemaps: /sitemap_index.xml lists one per post type.
The harvest scope is the item families (magic, thing, creature, place, event)
plus the seven-novel chapter source pages; characters and every other type
stay out of this pass (see docs/lexicon-canon-index.md, Site anatomy).

Chapters are generated from the corpus code table, not read from the source
sitemap: two canonical chapters (`gf12`, `dh33`) are absent there because the
site aliased their slugs (`gf12-2`, `dh33-the-princes-tale`) behind 301s. The
fetcher follows redirects, so the generated canonical urls resolve correctly
and the chapter identity comes from the url, not the slug.

Network access is injected so discovery is testable offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.ingest.lexicon.codes import NOVEL_CHAPTER_COUNTS

BASE = "https://www.hp-lexicon.org"
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")

ENTRY_TYPES = ("magic", "thing", "creature", "place", "event")
CODE_BY_BOOK = {1: "ps", 2: "cs", 3: "pa", 4: "gf", 5: "op", 6: "hbp", 7: "dh"}
SITEMAPS = {
    "magic": f"{BASE}/magic-sitemap.xml",
    "thing-1": f"{BASE}/thing-sitemap.xml",
    "thing-2": f"{BASE}/thing-sitemap2.xml",
    "thing-3": f"{BASE}/thing-sitemap3.xml",
    "creature": f"{BASE}/creature-sitemap.xml",
    "place": f"{BASE}/place-sitemap.xml",
    "event-1": f"{BASE}/event-sitemap.xml",
    "event-2": f"{BASE}/event-sitemap2.xml",
}


@dataclass(frozen=True)
class QueueItem:
    """One url to fetch, tagged with its harvest kind and family."""

    url: str
    kind: str  # entry | chapter
    family: str  # magic | thing | creature | place | event | novel


def parse_locs(xml: str) -> list[str]:
    return LOC_RE.findall(xml)


def entry_type_of(url: str) -> str | None:
    """The five item families, excluding the family hub pages themselves
    (`/magic/`, `/thing/`, ...), which are archive listings, not entries."""
    for family in ENTRY_TYPES:
        prefix = f"{BASE}/{family}/"
        if url.startswith(prefix) and url[len(prefix) :].strip("/"):
            return family
    return None


def novel_chapter_queue() -> list[QueueItem]:
    """All 198 chapter urls plus the Deathly Hallows epilogue, generated from
    the corpus chapter counts. Two of these (gf12, dh33) 301-redirect to
    aliased slugs; the fetcher follows the redirect and the identity is taken
    from the generated url, so the alias is harmless."""
    items: list[QueueItem] = []
    for book, code in CODE_BY_BOOK.items():
        for chapter in range(1, NOVEL_CHAPTER_COUNTS[book] + 1):
            items.append(
                QueueItem(
                    url=f"{BASE}/source/the-harry-potter-novels/{code}/{code}{chapter}/",
                    kind="chapter",
                    family="novel",
                )
            )
    items.append(
        QueueItem(
            url=f"{BASE}/source/the-harry-potter-novels/dh/dhe/",
            kind="chapter",
            family="novel",
        )
    )
    return items


def build_queue(sitemap_bodies: dict[str, str]) -> list[QueueItem]:
    """Turn {sitemap-name: xml} into the entry work queue, order-stable and
    deduped, then append the generated novel chapters.

    Non-entry urls (category, author, other-canon source pages) are dropped.
    """
    queue: list[QueueItem] = []
    seen: set[str] = set()
    for xml in sitemap_bodies.values():
        for url in parse_locs(xml):
            if url in seen:
                continue
            entry_type = entry_type_of(url)
            if entry_type is None:
                continue
            seen.add(url)
            queue.append(QueueItem(url=url, kind="entry", family=entry_type))
    for item in novel_chapter_queue():
        if item.url in seen:
            continue
        seen.add(item.url)
        queue.append(item)
    return queue
