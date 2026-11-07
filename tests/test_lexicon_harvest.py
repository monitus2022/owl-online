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
