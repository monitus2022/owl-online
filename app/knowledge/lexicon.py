"""Canon-index resolver: the Lexicon harvest joined and resolved to chunks.

Input: the gitignored harvest artifacts (`data/lexicon/entries.jsonl`,
`citations.jsonl`, `chapter_index.jsonl`, #126) plus our own corpus chunks.
Output: `canon_index.jsonl`, one row per (entry, book, chapter) edge with:

- agreement: `both` (the entry cites the chapter AND the chapter's
  Related-Entries tab lists the entry), `forward-only` (citation only),
  `reverse-only` (editor tab only - a hint, never evidence on its own);
- sources: whether the article text or the sidebar widget produced the
  forward edge; an edge present only in the sidebar is a disagreement-queue
  item for a human (`docs/lexicon-canon-index.md`);
- candidates: chunks inside the edge's chapter (or the whole book for a
  book-level citation) whose text contains one of the entry's match phrases.
  The incantation is preferred over the title because rare tokens do not
  collapse into prose noise (the "Boot"/"Jumper" precision risk from the
  plan).

No book text is persisted: each candidate carries the chunk id, the chunk
text hash (sha256[:16], the same shape as the index builder and
`chunk_text_hash`), and a [start, end) span. The pack builder reconstructs
the quote by slicing the corpus at build time, so copyrighted text lives in
one place - the gitignored corpus - not in this derived index.

The epilogue rule is pinned here: a `DHE` citation and the `/dh/dhe/` tab
both resolve to book 7 chapter 36 from chunk `b7-c36-0103` on (settled by
the #125 spike).

Deterministic: no model calls, no randomness, stable ordering everywhere.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.schemas import Chunk

NOVEL_BY_CODE = {"PS": 1, "CS": 2, "PA": 3, "GF": 4, "OP": 5, "HBP": 6, "DH": 7}

# The epilogue lives at the tail of book 7 chapter 36; its heading block
# starts inside this chunk (#125 spike, docs/lexicon-canon-index.md). DHE
# and the /dh/dhe/ tab resolve to chapter 36 from this chunk ordinal on.
EPILOGUE_BOOK = 7
EPILOGUE_CHAPTER = 36
EPILOGUE_FIRST_ORDINAL = 103

AGREEMENTS = ("both", "forward-only", "reverse-only")

# Reviewable caps: a phrase hitting dozens of chunks is a hint for a human,
# not a pile of source refs.
MAX_CANDIDATES_PER_EDGE = 8
MAX_MATCH_SPAN_CHARS = 220

_FAMILY_CANON = {
    "magic": "magic",
    "thing": "thing",
    "things": "thing",
    "creature": "creature",
    "creatures": "creature",
    "place": "place",
    "places": "place",
    "location": "place",
    "locations": "place",
    "event": "event",
    "events": "event",
}
_HREF_RE = re.compile(r"/([a-z-]+)/([a-z0-9-]+)/?$")


@dataclass(frozen=True)
class LexiconEntry:
    """One harvested entry: identity plus its match phrases."""

    key: str  # canonical family/slug
    family: str
    slug: str
    title: str
    incantation: str = ""

    @property
    def match_phrases(self) -> tuple[str, ...]:
        """Preferred-first: the incantation (rare token, high precision),
        then the bare title phrase with a leading article stripped. An
        incantation field that is really an editorial sentence (thin pages)
        is not a match phrase."""
        phrases: list[str] = []
        inc = self.incantation.strip()
        if (
            inc
            and len(inc.split()) <= 3
            and re.fullmatch(r"[A-Za-z][A-Za-z !'-]*", inc)
        ):
            phrases.append(inc.casefold())
        title = re.sub(r"^(the|a|an)\s+", "", self.title.strip(), flags=re.IGNORECASE)
        if title and title.casefold() not in phrases:
            phrases.append(title.casefold())
        return tuple(phrases)


@dataclass(frozen=True)
class Candidate:
    """One chunk that plausibly grounds an (entry, chapter) edge."""

    chunk_id: str
    text_hash: str
    span: tuple[int, int]
    phrase: str  # which match phrase hit


@dataclass(frozen=True)
class EdgeKey:
    entry_key: str
    book: int
    chapter: int | None  # None = book-level citation (a bare whole-book code)
    epilogue: bool = False


@dataclass(frozen=True)
class CanonEdge:
    """The resolved unit of the canon index."""

    key: EdgeKey
    family: str
    title: str
    agreement: str
    sources: tuple[str, ...]  # article, sidebar, tab
    candidates: tuple[Candidate, ...] = ()
    low_precision: bool = False  # more matches than the cap carries

    @property
    def resolved(self) -> bool:
        return bool(self.candidates)


def chunk_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def entry_key_from_href(href: str) -> str | None:
    """Map an entry href (article link or Related-Entries tab) to the
    canonical family/slug key; None for families the index does not carry."""
    m = _HREF_RE.search(href)
    if not m:
        return None
    family = _FAMILY_CANON.get(m.group(1))
    if family is None:
        return None
    return f"{family}/{m.group(2)}"


def entry_key_from_url(url: str) -> str | None:
    return entry_key_from_href(url)


def load_entries(path: Path) -> dict[str, LexiconEntry]:
    entries: dict[str, LexiconEntry] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = entry_key_from_url(row["url"])
        if key is None:
            continue
        entries[key] = LexiconEntry(
            key=key,
            family=row["family"],
            slug=row["slug"],
            title=row["title"],
            incantation=row.get("incantation", ""),
        )
    return entries


def forward_edges(citations_path: Path) -> dict[EdgeKey, set[str]]:
    """Books-bucket, valid-chapter citations keyed by edge.

    Returns {EdgeKey: {article|sidebar}}; `bare`/`anchor`/`href` origins are
    all article-level. Unknown entry keys and whole-book-only rows with no
    book number are skipped (they are secondary or excluded rows).
    """
    out: dict[EdgeKey, set[str]] = defaultdict(set)
    for line in citations_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["bucket"] != "books" or not row.get("valid_chapter", True):
            continue
        if row.get("book_num") is None:
            continue
        entry_key = entry_key_from_url(row["entry_url"])
        if entry_key is None:
            continue
        edge = EdgeKey(
            entry_key=entry_key,
            book=row["book_num"],
            chapter=row.get("chapter_num"),
            epilogue=bool(row.get("is_epilogue")),
        )
        out[edge].add("sidebar" if row["origin"] == "sidebar" else "article")
    return dict(out)


def reverse_edges(chapter_index_path: Path) -> set[EdgeKey]:
    """Entry keys listed in the chapter pages' Related-Entries tabs."""
    edges: set[EdgeKey] = set()
    for line in chapter_index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        book = NOVEL_BY_CODE.get(row["code"])
        if book is None:
            continue
        chapter = EPILOGUE_CHAPTER if row["is_epilogue"] else row["chapter_num"]
        if chapter is None:
            continue
        for group, _title, href in row["related"]:
            if _FAMILY_CANON.get(group) is None:
                continue
            entry_key = entry_key_from_href(href)
            if entry_key is None:
                continue
            edges.add(
                EdgeKey(
                    entry_key=entry_key,
                    book=book,
                    chapter=chapter,
                    epilogue=bool(row["is_epilogue"]),
                )
            )
    return edges


def group_chunks(chunks: list[Chunk]) -> dict[tuple[int, int], list[Chunk]]:
    """(book, chapter) -> chunks in document order (chunk ids sort by
    construction, so ordering is stable)."""
    grouped: dict[tuple[int, int], list[Chunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[(chunk.metadata.book_num, chunk.metadata.chapter_num)].append(chunk)
    for bucket in grouped.values():
        bucket.sort(key=lambda c: c.id)
    return grouped


def _chunk_ordinal(chunk_id: str) -> int:
    return int(chunk_id.rsplit("-", 1)[-1])


def _match_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    """Word-boundary, case-insensitive hits with plural tolerance (`charm`
    hits "charms"), extended to the sentence end (capped) so a span covers a
    usable quote without regex on prose."""
    spans: list[tuple[int, int]] = []
    pattern = re.compile(rf"\b{re.escape(phrase)}(?:e?s)?\b", re.IGNORECASE)
    for m in pattern.finditer(text):
        start = m.start()
        limit = min(len(text), start + MAX_MATCH_SPAN_CHARS)
        end = m.end()
        sentence = re.search(r"[.!?]", text[end:limit])
        end = end + sentence.end() if sentence else min(limit, end + 40)
        spans.append((start, min(end, limit)))
    return spans


def resolve_candidates(
    entry: LexiconEntry,
    edge: EdgeKey,
    grouped: dict[tuple[int, int], list[Chunk]],
) -> tuple[tuple[Candidate, ...], bool]:
    """Match the entry's phrases against the edge's chapter (or whole book).

    Phrase priority: the first phrase with any hit wins; earlier phrases
    (incantation) are preferred over later ones (title). Returns (candidates,
    low_precision); low_precision is True when total hits exceed the cap.
    """
    if edge.chapter is None:
        pool = [c for (b, _), cs in grouped.items() if b == edge.book for c in cs]
    elif edge.epilogue:
        pool = [
            c
            for c in grouped.get((EPILOGUE_BOOK, EPILOGUE_CHAPTER), [])
            if _chunk_ordinal(c.id) >= EPILOGUE_FIRST_ORDINAL
        ]
    else:
        pool = grouped.get((edge.book, edge.chapter), [])
    for phrase in entry.match_phrases:
        hits: list[Candidate] = []
        for chunk in pool:
            for start, end in _match_spans(chunk.text, phrase):
                hits.append(
                    Candidate(
                        chunk_id=chunk.id,
                        text_hash=chunk_text_hash(chunk.text),
                        span=(start, end),
                        phrase=phrase,
                    )
                )
                if len(hits) > MAX_CANDIDATES_PER_EDGE:
                    return tuple(hits[:MAX_CANDIDATES_PER_EDGE]), True
        if hits:
            return tuple(hits), False
    return (), False


def build_canon_index(
    entries: dict[str, LexiconEntry],
    forward: dict[EdgeKey, set[str]],
    reverse: set[EdgeKey],
    grouped: dict[tuple[int, int], list[Chunk]],
) -> list[CanonEdge]:
    """Join forward citations and reverse tabs, then resolve candidates.

    A reverse-only edge for an entry we never harvested is still recorded
    (unresolved): the disagreement is visible, never dropped.
    """
    edges: list[CanonEdge] = []
    ordered = sorted(
        set(forward) | reverse,
        key=lambda k: (k.entry_key, k.book, k.epilogue, k.chapter is None, k.chapter or 0),
    )
    for key in ordered:
        entry = entries.get(key.entry_key)
        title = entry.title if entry else key.entry_key.split("/", 1)[-1]
        family = entry.family if entry else key.entry_key.split("/", 1)[0]
        sources = tuple(sorted(forward.get(key, set()) | ({"tab"} if key in reverse else set())))
        has_forward = key in forward
        has_reverse = key in reverse
        if has_forward and has_reverse:
            agreement = "both"
        elif has_forward:
            agreement = "forward-only"
        else:
            agreement = "reverse-only"
        candidates: tuple[Candidate, ...] = ()
        low = False
        if entry is not None:
            candidates, low = resolve_candidates(entry, key, grouped)
        edges.append(
            CanonEdge(
                key=key,
                family=family,
                title=title,
                agreement=agreement,
                sources=sources,
                candidates=candidates,
                low_precision=low,
            )
        )
    return edges


def canon_row(edge: CanonEdge) -> dict:
    """JSONL-safe projection (dataclasses to plain values)."""
    return {
        "entry_key": edge.key.entry_key,
        "family": edge.family,
        "title": edge.title,
        "book": edge.key.book,
        "chapter": edge.key.chapter,
        "epilogue": edge.key.epilogue,
        "agreement": edge.agreement,
        "sources": list(edge.sources),
        "low_precision": edge.low_precision,
        "candidates": [
            {
                "chunk_id": c.chunk_id,
                "text_hash": c.text_hash,
                "span": list(c.span),
                "phrase": c.phrase,
            }
            for c in edge.candidates
        ],
    }


def summarize(edges: list[CanonEdge]) -> dict:
    """Aggregate counts only - no candidate text, safe to print or commit."""
    by_agreement: dict[str, int] = {a: 0 for a in AGREEMENTS}
    by_family: dict[str, int] = defaultdict(int)
    resolved = 0
    low_precision = 0
    sidebar_only = 0
    for edge in edges:
        by_agreement[edge.agreement] += 1
        by_family[edge.family] += 1
        if edge.resolved:
            resolved += 1
        if edge.low_precision:
            low_precision += 1
        sources = set(edge.sources)
        if "sidebar" in sources and "article" not in sources:
            sidebar_only += 1
    return {
        "edges": len(edges),
        "by_agreement": by_agreement,
        "by_family": dict(sorted(by_family.items())),
        "resolved": resolved,
        "low_precision": low_precision,
        "sidebar_only": sidebar_only,
    }


__all__ = [
    "AGREEMENTS",
    "CanonEdge",
    "Candidate",
    "EdgeKey",
    "LexiconEntry",
    "build_canon_index",
    "canon_row",
    "chunk_text_hash",
    "entry_key_from_href",
    "forward_edges",
    "group_chunks",
    "load_entries",
    "resolve_candidates",
    "reverse_edges",
    "summarize",
]
