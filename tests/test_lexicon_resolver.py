"""Tests for the canon-index resolver (#127) on synthetic fixtures.

Chunks are invented sentences; the resolver is exercised against them so no
corpus text enters git. Hashes are computed with the same helper the index
builder uses, keeping the join honest.
"""

import json
from dataclasses import replace
from pathlib import Path

from app.knowledge.lexicon import (
    EPILOGUE_FIRST_ORDINAL,
    CanonEdge,
    EdgeKey,
    LexiconEntry,
    build_canon_index,
    canon_row,
    chunk_text_hash,
    entry_key_from_href,
    forward_edges,
    group_chunks,
    load_entries,
    resolve_candidates,
    reverse_edges,
    sample_edges,
    summarize,
    verify_edges,
)
from app.schemas import Chunk, ChunkMetadata

HREF = "https://www.hp-lexicon.org/magic/summoning-charm/"


def _chunk(cid: str, text: str, book: int = 4, chapter: int = 6) -> Chunk:
    return Chunk(
        id=cid,
        text=text,
        metadata=ChunkMetadata(
            book_num=book,
            chapter_num=chapter,
            book_name=f"Book {book}",
            chapter_name=f"Ch {chapter}",
        ),
    )


def _entries(tmp_path: Path) -> dict:
    rows = [
        {
            "url": HREF,
            "slug": "summoning-charm",
            "family": "magic",
            "title": "Summoning Charm",
            "incantation": "Accio",
        },
        {
            "url": "https://www.hp-lexicon.org/thing/boot/",
            "slug": "boot",
            "family": "thing",
            "title": "Boot",
            "incantation": "",
        },
    ]
    path = tmp_path / "entries.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return load_entries(path)


# --- keys and phrase rules ---------------------------------------------------


def test_href_family_canonicalisation():
    assert entry_key_from_href("/magic/summoning-charm/") == "magic/summoning-charm"
    assert entry_key_from_href("/thing/portkey/") == "thing/portkey"
    assert entry_key_from_href("/creature/niffler/") == "creature/niffler"
    # plural tab names normalise through the same map
    assert entry_key_from_href("/creatures/niffler/") == "creature/niffler"
    # nested geography urls key on the family segment and the final slug
    assert (
        entry_key_from_href("/place/great-britain/england/devon/the-burrow/")
        == "place/the-burrow"
    )
    # families outside the index (characters, essays) do not become edges
    assert entry_key_from_href("/character/harry-potter/") is None
    assert entry_key_from_href("/2016/essay/") is None


def test_match_phrases_prefer_incantation_and_drop_editorial_sentences(tmp_path):
    entries = _entries(tmp_path)
    accio = entries["magic/summoning-charm"]
    assert accio.match_phrases == ("accio", "summoning charm")
    boot = entries["thing/boot"]
    assert boot.match_phrases == ("boot",)


def test_long_incantation_field_is_not_a_match_phrase():
    """Thin entries sometimes store a whole sentence under Incantation; it
    must not become a search phrase."""
    from app.knowledge.lexicon import LexiconEntry

    e = LexiconEntry(
        key="magic/x",
        family="magic",
        slug="x",
        title="X Charm",
        incantation="The official pronunciation from Scholastic is unclear here",
    )
    assert e.match_phrases == ("x charm",)


# --- candidate resolution -----------------------------------------------------


def test_incantation_hit_yields_hashed_span(tmp_path):
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c06-0011", "She said, \u201cAccio!\u201d and the toffees zoomed out.", 4, 6)
    grouped = group_chunks([chunk])
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    candidates, low, _total = resolve_candidates(entries[edge.entry_key], edge, grouped)
    assert not low
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.chunk_id == "b4-c06-0011"
    assert cand.phrase == "accio"
    assert cand.text_hash == chunk_text_hash(chunk.text)
    start, end = cand.span
    assert chunk.text[start:end].casefold().startswith("accio")
    assert end - start <= 220


def test_book_level_edge_scans_every_chapter(tmp_path):
    entries = _entries(tmp_path)
    grouped = group_chunks(
        [
            _chunk("b4-c01-0000", "nothing here", 4, 1),
            _chunk("b4-c20-0005", "Accio brought the broom to him", 4, 20),
        ]
    )
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=None)
    candidates, _, _total = resolve_candidates(entries[edge.entry_key], edge, grouped)
    assert [c.chunk_id for c in candidates] == ["b4-c20-0005"]


def test_title_falls_back_only_when_incantation_misses(tmp_path):
    entries = _entries(tmp_path)
    grouped = group_chunks([_chunk("b4-c06-0001", "The summoning charm is rare prose.", 4, 6)])
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    candidates, _, _total = resolve_candidates(entries[edge.entry_key], edge, grouped)
    assert candidates[0].phrase == "summoning charm"


def test_plural_tolerance_in_phrase_match(tmp_path):
    """The books say "the summoning charms" while the entry title is singular;
    a plural hit is the same quote, not a different phrase."""
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c06-0003", "Mrs Weasley used summoning charms on the toffees.", 4, 6)
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    candidates, _, _total = resolve_candidates(entries[edge.entry_key], edge, group_chunks([chunk]))
    assert [c.phrase for c in candidates] == ["summoning charm"]
    start, end = candidates[0].span
    assert chunk.text[start:end].casefold().startswith("summoning charms")


def test_common_noun_edge_is_capped_and_flagged(tmp_path):
    entries = _entries(tmp_path)
    chunks = [
        _chunk(f"b2-c10-{i:04d}", f"A boot sat by the door number {i}.", 2, 10) for i in range(12)
    ]
    edge = EdgeKey(entry_key="thing/boot", book=2, chapter=10)
    candidates, low, _total = resolve_candidates(entries["thing/boot"], edge, group_chunks(chunks))
    assert low
    assert len(candidates) == 8


def test_epilogue_slice_excludes_pre_marker_chunks(tmp_path):
    entries = _entries(tmp_path)
    marker_ok = _chunk(
        f"b7-c36-{EPILOGUE_FIRST_ORDINAL:04d}", "Summoning charm prose after the marker", 7, 36
    )
    before = _chunk("b7-c36-0050", "Summoning charm earlier in the chapter", 7, 36)
    edge = EdgeKey(entry_key="magic/summoning-charm", book=7, chapter=36, epilogue=True)
    candidates, _, _total = resolve_candidates(
        entries[edge.entry_key], edge, group_chunks([before, marker_ok])
    )
    assert [c.chunk_id for c in candidates] == [marker_ok.id]


# --- join -----------------------------------------------------------------------


def test_forward_and_reverse_become_both_agreement(tmp_path):
    citations = tmp_path / "citations.jsonl"
    citations.write_text(
        json.dumps(
            {
                "entry_url": HREF,
                "bucket": "books",
                "valid_chapter": True,
                "origin": "href",
                "book_num": 4,
                "chapter_num": 6,
                "code": "GF6",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    chapters = tmp_path / "chapter_index.jsonl"
    chapters.write_text(
        json.dumps(
            {
                "url": "https://www.hp-lexicon.org/source/the-harry-potter-novels/gf/gf6/",
                "code": "GF",
                "chapter_num": 6,
                "is_epilogue": False,
                "related": [["magic", "Summoning Charm", HREF]],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    forward = forward_edges(citations)
    reverse = reverse_edges(chapters)
    edge_key = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    assert edge_key in forward and edge_key in reverse
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c06-0002", "Accio flew the toffees into her hand", 4, 6)
    edges = build_canon_index(entries, forward, reverse, group_chunks([chunk]))
    assert len(edges) == 1
    resolved = edges[0]
    assert resolved.agreement == "both"
    assert set(resolved.sources) == {"article", "tab"}
    assert resolved.resolved


def test_sidebar_only_edge_is_flagged_for_review(tmp_path):
    """An edge found only in the Sources sidebar (never in the article text)
    is recorded, never dropped, and counted by the summary."""
    key = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=20)
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c20-0001", "He whispered Accio for his broom", 4, 20)
    edges = build_canon_index(entries, {key: {"sidebar"}}, set(), group_chunks([chunk]))
    summary = summarize(edges)
    assert summary["sidebar_only"] == 1
    assert edges[0].agreement == "forward-only"  # sidebar is still a forward source


def test_reverse_only_edge_without_harvested_entry_is_kept_unresolved(tmp_path):
    entries = _entries(tmp_path)
    orphan = EdgeKey(entry_key="magic/not-harvested", book=1, chapter=2)
    pool = group_chunks([_chunk("b1-c02-0000", "x", 1, 2)])
    edges = build_canon_index(entries, {}, {orphan}, pool)
    assert len(edges) == 1
    assert edges[0].agreement == "reverse-only"
    assert not edges[0].resolved
    assert edges[0].title == "not-harvested"


def test_canon_row_is_jsonl_round_trip_safe(tmp_path):
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c06-0001", "Accio!", 4, 6)
    key = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    edges = build_canon_index(entries, {key: {"article"}}, set(), group_chunks([chunk]))
    row = canon_row(edges[0])
    again = json.loads(json.dumps(row))
    assert again["candidates"][0]["chunk_id"] == "b4-c06-0001"
    assert again["epilogue"] is False


def test_build_canon_index_order_is_deterministic(tmp_path):
    entries = _entries(tmp_path)
    a = EdgeKey(entry_key="magic/a-thing", book=1, chapter=1)
    b = EdgeKey(entry_key="magic/b-thing", book=1, chapter=1)
    z = EdgeKey(entry_key="thing/z-boot", book=2, chapter=None)
    edges = build_canon_index(entries, {b: {"article"}, z: {"article"}, a: {"article"}}, set(), {})
    assert [e.key.entry_key for e in edges] == ["magic/a-thing", "magic/b-thing", "thing/z-boot"]


def test_dhe_edge_merges_with_dhe_tab_but_not_with_plain_dh36(tmp_path):
    """The epilogue-flag rule at join level: a DHE citation and the /dh/dhe/
    tab must agree as both; a plain DH36 citation stays a separate,
    forward-only edge."""
    entries = _entries(tmp_path)
    citations = tmp_path / "citations.jsonl"
    citations.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {
                    "entry_url": HREF,
                    "bucket": "books",
                    "valid_chapter": True,
                    "origin": "href",
                    "book_num": 7,
                    "chapter_num": 36,
                    "code": "DHE",
                    "is_epilogue": True,
                },
                {
                    "entry_url": HREF,
                    "bucket": "books",
                    "valid_chapter": True,
                    "origin": "href",
                    "book_num": 7,
                    "chapter_num": 36,
                    "code": "DH36",
                    "is_epilogue": False,
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    chapters = tmp_path / "chapter_index.jsonl"
    chapters.write_text(
        json.dumps(
            {
                "url": "https://www.hp-lexicon.org/source/the-harry-potter-novels/dh/dhe/",
                "code": "DH",
                "chapter_num": None,
                "is_epilogue": True,
                "related": [["magic", "Summoning Charm", HREF]],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    forward = forward_edges(citations)
    reverse = reverse_edges(chapters)
    edges = build_canon_index(entries, forward, reverse, {})
    by_key = {e.key: e for e in edges}
    dhe = by_key[EdgeKey("magic/summoning-charm", 7, 36, epilogue=True)]
    plain = by_key[EdgeKey("magic/summoning-charm", 7, 36, epilogue=False)]
    assert dhe.agreement == "both"
    assert plain.agreement == "forward-only"


def test_cap_boundary_exactly_eight_is_not_flagged(tmp_path):
    entries = _entries(tmp_path)
    chunks = [
        _chunk(f"b2-c10-{i:04d}", f"A boot sat by the door number {i}.", 2, 10) for i in range(8)
    ]
    edge = EdgeKey(entry_key="thing/boot", book=2, chapter=10)
    candidates, low, total = resolve_candidates(entries["thing/boot"], edge, group_chunks(chunks))
    assert len(candidates) == 8 and total == 8 and low is False


def test_incantation_phrase_wins_when_both_hit(tmp_path):
    entries = _entries(tmp_path)
    chunk = _chunk("b4-c06-0009", "She said Accio and the summoning charm flew.", 4, 6)
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    candidates, _, total = resolve_candidates(entries[edge.entry_key], edge, group_chunks([chunk]))
    assert {c.phrase for c in candidates} == {"accio"}
    assert total == 1


def test_unparseable_entry_urls_are_counted_not_dropped(tmp_path):
    citations = tmp_path / "citations.jsonl"
    citations.write_text(
        json.dumps(
            {
                "entry_url": "https://www.hp-lexicon.org/magiccategory/spells/",
                "bucket": "books",
                "valid_chapter": True,
                "origin": "href",
                "book_num": 4,
                "chapter_num": 6,
                "code": "GF6",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    skipped: list[str] = []
    forward = forward_edges(citations, skipped)
    assert forward == {}
    assert skipped == ["https://www.hp-lexicon.org/magiccategory/spells/"]


def test_novel_table_matches_the_harvest_grammar():
    """Guard the duplication a layering rule forces: knowledge cannot import
    the ingest package, so the two code tables must agree."""
    from app.knowledge.lexicon import NOVEL_BY_CODE as RESOLVER_TABLE
    from app.pipeline.ingest.lexicon.codes import NOVEL_BY_CODE as GRAMMAR_TABLE

    assert RESOLVER_TABLE == GRAMMAR_TABLE


def test_underscore_slug_and_hub_rejection():
    # the real lilys_letter slug that exposed the hyphen-only regex
    assert entry_key_from_href("/thing/lilys_letter/") == "thing/lilys_letter"
    # a bare family hub page is not an entry
    assert entry_key_from_href("/magic/") is None
    assert entry_key_from_href("https://www.hp-lexicon.org/place/") is None


# --- verify_edges --------------------------------------------------------------


def _edge_with_candidate():
    chunk = _chunk("b4-c06-0007", "Accio summon the broom", 4, 6)
    edge = EdgeKey(entry_key="magic/summoning-charm", book=4, chapter=6)
    candidates, _, _total = resolve_candidates(
        LexiconEntry(key=edge.entry_key, family="magic", slug="summoning-charm",
                     title="Summoning Charm", incantation="Accio"),
        edge,
        group_chunks([chunk]),
    )
    return (
        [CanonEdge(key=edge, family="magic", title="Summoning Charm",
                   agreement="forward-only", sources=("article",), candidates=candidates)],
        {chunk.id: chunk},
    )


def test_verify_edges_clean_on_honest_index():
    edges, chunks = _edge_with_candidate()
    assert verify_edges(edges, chunks) == []


def test_verify_edges_catches_tampering():
    edges, chunks = _edge_with_candidate()
    cand = edges[0].candidates[0]

    tampered_hash = replace(edges[0], candidates=[replace(cand, text_hash="0" * 16)])
    assert any("text hash" in p for p in verify_edges([tampered_hash], chunks))

    tampered_span = replace(edges[0], candidates=[replace(cand, span=(0, 1))])
    assert any("span" in p for p in verify_edges([tampered_span], chunks))

    assert any("not in corpus" in p for p in verify_edges(edges, {}))

    # the chunk exists but belongs to another chapter: outside the edge pool
    moved = {cand.chunk_id: _chunk(cand.chunk_id, "Accio summon the broom", 4, 9)}
    problems = verify_edges(edges, moved)
    assert any("outside the edge" in p for p in problems)


def test_sample_edges_deterministic_and_bounded():
    edges = []
    for i in range(60):
        edges.append(
            CanonEdge(
                key=EdgeKey(entry_key=f"magic/e{i:02d}", book=1, chapter=1),
                family="magic",
                title=f"E{i:02d}",
                agreement="both" if i % 2 else "forward-only",
                sources=("article", "tab"),
            )
        )
    first = sample_edges(edges, 25)
    second = sample_edges(edges, 25)
    assert [e.key.entry_key for e in first["both"]] == [e.key.entry_key for e in second["both"]]
    assert len(first["both"]) <= 25 and len(first["forward-only"]) <= 25
    # n larger than the pool returns the whole pool, not padding
    big = sample_edges(edges, 500)
    assert len(big["both"]) == 30
    # a mid-size pool (n <= size < 2n) must return exactly n, spread evenly
    both40 = [replace(e, agreement="both") for e in edges[:40]]
    mid = sample_edges(both40, 25)["both"]
    keys = [e.key.entry_key for e in mid]
    assert len(keys) == 25
    assert keys == sorted(keys)  # order-stable
    assert keys[-1] == "magic/e38"  # reaches the pool tail, not first-n
    assert sample_edges(both40, 25)["both"] == mid  # deterministic


def test_sample_edges_zero_requests_is_empty():
    assert sample_edges([], 0) == {"both": [], "forward-only": []}
