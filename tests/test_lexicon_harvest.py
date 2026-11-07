"""Offline tests for the Lexicon harvester modules (#126).

No network: the sitemap xml, the fetcher opener and the clock are all
injected. Fixtures are synthetic markup skeletons with invented text.
"""

import json
from datetime import UTC, datetime

import pytest

from app.pipeline.ingest.lexicon.discovery import (
    QueueItem,
    build_queue,
    entry_type_of,
    novel_chapter_queue,
    parse_locs,
)
from app.pipeline.ingest.lexicon.fetch import Fetcher
from app.pipeline.ingest.lexicon.harvest import harvest

BASE = "https://www.hp-lexicon.org"


def _sitemap(urls):
    return "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>"


def test_parse_locs_extracts_urls():
    assert parse_locs(_sitemap([f"{BASE}/magic/a/", f"{BASE}/thing/b/"])) == [
        f"{BASE}/magic/a/",
        f"{BASE}/thing/b/",
    ]


def test_entry_type_filter():
    assert entry_type_of(f"{BASE}/magic/accio/") == "magic"
    assert entry_type_of(f"{BASE}/thing/portkey/") == "thing"
    assert entry_type_of(f"{BASE}/source/other-canon/pm/") is None


def test_novel_chapter_queue_is_generated_from_corpus_counts():
    chapters = novel_chapter_queue()
    assert len(chapters) == 198 + 1  # 198 chapters plus the DH epilogue
    assert all(c.kind == "chapter" and c.family == "novel" for c in chapters)
    assert f"{BASE}/source/the-harry-potter-novels/gf/gf12/" in {c.url for c in chapters}
    assert f"{BASE}/source/the-harry-potter-novels/dh/dhe/" in {c.url for c in chapters}


def test_build_queue_filters_dedupes_and_appends_chapters():
    bodies = {
        "magic": _sitemap([f"{BASE}/magic/a/", f"{BASE}/magiccategory/spells/"]),
        "thing-1": _sitemap([f"{BASE}/thing/b/"]),
        "thing-2": _sitemap([f"{BASE}/thing/b/", f"{BASE}/thing/c/"]),
    }
    queue = build_queue(bodies)
    entries = [(q.url, q.kind, q.family) for q in queue if q.kind == "entry"]
    assert entries == [
        (f"{BASE}/magic/a/", "entry", "magic"),
        (f"{BASE}/thing/b/", "entry", "thing"),
        (f"{BASE}/thing/c/", "entry", "thing"),
    ]
    # all 199 novel chapters are appended deterministically
    assert [q.kind for q in queue].count("chapter") == 199


def test_fetcher_caches_and_records_hash_and_date(tmp_path):
    calls = []

    def opener(url):
        calls.append(url)
        return b"<html><body><h1>x</h1></body></html>"

    slept = []
    fetcher = Fetcher(
        tmp_path,
        opener=opener,
        sleep=slept.append,
        clock=lambda: datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC),
    )
    url = f"{BASE}/magic/accio/"
    record, html = fetcher.fetch(url)
    assert not record.from_cache
    assert record.fetched_at == "2026-11-07T12:00:00+00:00"
    assert len(record.sha256) == 64
    assert slept and slept[0] >= 1.0  # politeness enforced once, on a live fetch

    record2, html2 = fetcher.fetch(url)
    assert record2.from_cache
    assert html2 == html
    assert record2.fetched_at == record.fetched_at  # sidecar keeps the date
    assert len(calls) == 1  # the second fetch never hits the network


def test_fetcher_retries_once_then_raises(tmp_path):
    attempts = []

    def opener(url):
        attempts.append(url)
        raise OSError("boom")

    slept = []
    fetcher = Fetcher(tmp_path, opener=opener, sleep=slept.append)
    with pytest.raises(RuntimeError):
        fetcher.fetch(f"{BASE}/magic/zzz/")
    assert len(attempts) == 2
    assert 5.0 in slept  # backoff between the two attempts


ENTRY_HTML = """
<html><body><h1>Test Charm</h1>
<p>Cited (<a href="/source/the-harry-potter-novels/gf/gf20">GF20</a>).</p>
<div class="related_container"></div>
</body></html>
"""

CHAPTER_HTML = """
<html><body><h1>The Portkey Field</h1>
<div class="data">Abbreviation <span>GF6: The Portkey Field</span></div>
<div class="data">Canonicity <span>Primary Canon</span></div>
<div class="relatedlink-container relatedlink-magic">
<a class="relatedlink related-magic" href="/magic/test-charm/">Test Charm</a>
</div>
</body></html>
"""


def test_harvest_writes_artifacts_and_summary(tmp_path):
    pages = {
        f"{BASE}/magic/test-charm/": ENTRY_HTML.encode(),
        f"{BASE}/source/the-harry-potter-novels/gf/gf6/": CHAPTER_HTML.encode(),
    }

    def opener(url):
        return pages[url]

    fetcher = Fetcher(tmp_path / "pages", opener=opener, sleep=lambda s: None)
    queue = [
        QueueItem(f"{BASE}/magic/test-charm/", "entry", "magic"),
        QueueItem(f"{BASE}/source/the-harry-potter-novels/gf/gf6/", "chapter", "novel"),
    ]
    summary = harvest(queue, tmp_path, fetcher)

    assert summary["entries"] == 1
    assert summary["chapters"] == 1
    assert summary["buckets"]["books"] == 1

    entries = [json.loads(x) for x in (tmp_path / "entries.jsonl").read_text().splitlines()]
    assert entries[0]["slug"] == "test-charm"
    assert entries[0]["family"] == "magic"
    chapters = [
        json.loads(x)
        for x in (tmp_path / "chapter_index.jsonl").read_text().splitlines()
    ]
    assert chapters[0]["abbreviation"] == "GF6: The Portkey Field"
    # fetch_index carries the etiquette record for every page.
    meta = [
        json.loads(x)
        for x in (tmp_path / "fetch_index.jsonl").read_text().splitlines()
    ]
    assert len(meta) == 2
    assert all(m["sha256"] for m in meta)


def test_harvest_flags_out_of_range_books_edges(tmp_path):
    page_html = """
    <html><body><h1>Scars</h1>
    <p>A broken link
    (<a href="/source/the-harry-potter-novels/dh/dh117">DH117</a>)
    and a real one
    (<a href="/source/the-harry-potter-novels/dh/dh17">DH17</a>).</p>
    <div class="related_container"></div>
    </body></html>
    """

    def opener(url):
        return page_html.encode()

    fetcher = Fetcher(tmp_path / "pages", opener=opener, sleep=lambda s: None)
    summary = harvest(
        [QueueItem(f"{BASE}/thing/scars/", "entry", "thing")], tmp_path, fetcher
    )
    assert summary["invalid_chapter_edges"] == 1
    rows = [
        json.loads(x)
        for x in (tmp_path / "citations.jsonl").read_text().splitlines()
    ]
    by = {r["code"]: r for r in rows}
    assert by["DH117"]["valid_chapter"] is False
    assert by["DH17"]["valid_chapter"] is True
    queued = [
        json.loads(x)
        for x in (tmp_path / "invalid_chapters.jsonl").read_text().splitlines()
    ]
    assert [q["code"] for q in queued] == ["DH117"]


def test_harvest_records_failures_by_page(tmp_path):
    def opener(url):
        raise OSError("network down")

    fetcher = Fetcher(tmp_path / "pages", opener=opener, sleep=lambda s: None)
    summary = harvest(
        [QueueItem(f"{BASE}/magic/broken/", "entry", "magic")], tmp_path, fetcher
    )
    assert summary["failures"] == 1
    failures = [
        json.loads(x)
        for x in (tmp_path / "harvest_failures.jsonl").read_text().splitlines()
    ]
    assert failures[0]["url"] == f"{BASE}/magic/broken/"
    assert failures[0]["stage"] == "fetch"


def test_parse_failure_names_the_page(tmp_path):
    """Done-when 3 is specifically about parse failures naming their page."""

    def opener(url):
        return b"<html><body>no title here</body></html>"

    fetcher = Fetcher(tmp_path / "pages", opener=opener, sleep=lambda s: None)
    summary = harvest(
        [QueueItem(f"{BASE}/thing/headless/", "entry", "thing")], tmp_path, fetcher
    )
    assert summary["failures"] == 1
    failures = [
        json.loads(x)
        for x in (tmp_path / "harvest_failures.jsonl").read_text().splitlines()
    ]
    assert failures[0]["stage"] == "parse"
    assert failures[0]["url"] == f"{BASE}/thing/headless/"


def test_zero_citation_is_reported_separately_from_failure(tmp_path):
    def opener(url):
        return b"<html><body><h1>Sweet</h1><p>no cites</p><footer></footer></body></html>"

    fetcher = Fetcher(tmp_path / "pages", opener=opener, sleep=lambda s: None)
    summary = harvest(
        [QueueItem(f"{BASE}/thing/silent/", "entry", "thing")], tmp_path, fetcher
    )
    assert summary["zero_citation_entries"] == 1
    assert summary["failures"] == 0


def test_fetch_metadata_survives_a_reparse(tmp_path):
    """The etiquette promise: the access date recorded at fetch time must
    survive later cache-only re-parses (#128 attribution depends on it)."""

    pages = {f"{BASE}/magic/accio/": ENTRY_HTML.encode()}

    def opener(url):
        return pages[url]

    out = tmp_path / "out"
    first = Fetcher(out / "pages", opener=opener, sleep=lambda s: None)
    harvest([QueueItem(f"{BASE}/magic/accio/", "entry", "magic")], out, first)
    meta1 = [json.loads(x) for x in (out / "fetch_index.jsonl").read_text().splitlines()]

    calls: list[str] = []

    def counting_opener(url):
        calls.append(url)
        raise AssertionError("must not hit the network on cache hits")

    second = Fetcher(out / "pages", opener=counting_opener, sleep=lambda s: None)
    harvest([QueueItem(f"{BASE}/magic/accio/", "entry", "magic")], out, second)
    meta2 = [json.loads(x) for x in (out / "fetch_index.jsonl").read_text().splitlines()]

    assert calls == []
    assert meta2[0]["fetched_at"] == meta1[0]["fetched_at"] != ""


def test_article_region_prefers_the_structural_stop_over_prose():
    """A stop marker appearing in prose must not truncate the article before
    the real Related-Entries boundary."""
    html = """
    <html><body><h1>Charm</h1>
    <p>Discussed beside The Harry Potter Canon in prose (GF34).</p>
    <p>Also (<a href="/source/the-harry-potter-novels/gf/gf35">GF35</a>).</p>
    <div class="related_container"></div>
    </body></html>
    """
    from app.pipeline.ingest.lexicon.parse import parse_entry_page

    page = parse_entry_page(html, f"{BASE}/magic/charm/")
    assert {c.code for c in page.citations} >= {"GF34", "GF35"}


def test_discovery_excludes_family_hub_pages():
    bodies = {"magic": _sitemap([f"{BASE}/magic/", f"{BASE}/magic/a/"])}
    queue = build_queue(bodies)
    entries = [q.url for q in queue if q.kind == "entry"]
    assert entries == [f"{BASE}/magic/a/"]
