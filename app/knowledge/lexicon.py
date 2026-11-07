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
the #125 spike). Note the chunk-granular asymmetry: a plain `DH36` citation
sees all of chapter 36 including the epilogue tail, while `DHE` starts at
the marker chunk. #128's review should know the difference is one-directional.

Known span limitation: the sentence extension cuts at the first [.!?] and
falls back to +40 characters, so abbreviations or ellipses can end a span
early and the fallback can stop mid-word. The hash pins the chunk text, so a
span is always safe to slice; only the quote's cosmetics suffer, and a pack
author adjusts while reviewing.

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
    total_hits: int = 0  # all hits for the winning phrase, before the cap

    @property
    def resolved(self) -> bool:
        return bool(self.candidates)


def chunk_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


_CANONICAL_FAMILIES = (
    "magic",
    "thing",
    "things",
    "creature",
    "creatures",
    "place",
    "places",
    "locations",
    "location",
    "event",
    "events",
)


def entry_key_from_href(href: str) -> str | None:
    """Map an entry href (article or sidebar url, or a Related-Entries tab)
    to the canonical family/slug key; None for families the index does not
    carry (characters, essays) or urls with no family segment.

    Place and creature urls nest under geography (`/place/.../the-burrow/`),
    so the family is the first path segment that is a known family, and the
    slug is the final segment - never a guessed last-two pair.
    """
    segments = [s for s in href.split("/") if s]
    family = None
    for segment in segments:
        if segment in _CANONICAL_FAMILIES:
            family = _FAMILY_CANON.get(segment)
            break
    if family is None or not segments:
        return None
    slug = segments[-1]
    if not re.fullmatch(r"[a-z0-9_-]+", slug):
        return None
    if slug == family:
        return None  # a bare family hub page (/magic/) is not an entry
    return f"{family}/{slug}"


def entry_key_from_url(url: str) -> str | None:
    return entry_key_from_href(url)


def load_entries(path: Path, skipped: list[str] | None = None) -> dict[str, LexiconEntry]:
    entries: dict[str, LexiconEntry] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        family = _FAMILY_CANON.get(row["family"])
        slug = row["url"].rstrip("/").rsplit("/", 1)[-1]
        key = f"{family}/{slug}" if family and slug else ""
        if not key:
            if skipped is not None:
                skipped.append(row["url"])
            continue
        entries[key] = LexiconEntry(
            key=key,
            family=family,
            slug=slug,
            title=row["title"],
            incantation=row.get("incantation", ""),
        )
    return entries


def forward_edges(
    citations_path: Path, skipped: list[str] | None = None
) -> dict[EdgeKey, set[str]]:
    """Books-bucket, valid-chapter citations keyed by edge.

    Returns {EdgeKey: {article|sidebar}}; `bare`/`anchor`/`href` origins are
    all article-level. Rows whose entry url does not parse into a harvested
    family are counted into `skipped` (never silently dropped).
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
            if skipped is not None:
                skipped.append(row["entry_url"])
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


def index_chunks(chunks: list[Chunk]) -> dict[str, Chunk]:
    """Chunk id -> chunk, for verification and quote reconstruction."""
    return {chunk.id: chunk for chunk in chunks}


def _phrase_re(phrase: str) -> re.Pattern[str]:
    """One builder for the match expression, used by both the matcher and
    the verifier: identical semantics is the point of verifying at all."""
    return re.compile(rf"\b{re.escape(phrase)}(?:e?s)?\b", re.IGNORECASE)


def _chunk_ordinal(chunk_id: str) -> int:
    tail = chunk_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isascii() and tail.isdigit() else -1  # a foreign id is never "after"


def _match_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    """Word-boundary, case-insensitive hits with plural tolerance (`charm`
    hits "charms"), extended to the sentence end (capped) so a span covers a
    usable quote without regex on prose."""
    spans: list[tuple[int, int]] = []
    pattern = _phrase_re(phrase)
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
) -> tuple[tuple[Candidate, ...], bool, int]:
    """Match the entry's phrases against the edge's chapter (or whole book).

    Phrase priority: the first phrase with any hit wins; earlier phrases
    (incantation) are preferred over later ones (title). Returns (candidates,
    low_precision, total_hits); low_precision is True when total hits exceed
    the cap, and candidates are truncated to the cap.
    """
    if edge.chapter is None:
        # Sort by (chapter, id) so truncation order survives a re-ingest that
        # presents chapters differently.
        pool = sorted(
            (c for (b, _), cs in grouped.items() if b == edge.book for c in cs),
            key=lambda c: (c.metadata.chapter_num, c.id),
        )
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
        if hits:
            retained = tuple(hits[:MAX_CANDIDATES_PER_EDGE])
            return retained, len(hits) > MAX_CANDIDATES_PER_EDGE, len(hits)
    return (), False, 0


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
        total = 0
        if entry is not None:
            candidates, low, total = resolve_candidates(entry, key, grouped)
        edges.append(
            CanonEdge(
                key=key,
                family=family,
                title=title,
                agreement=agreement,
                sources=sources,
                candidates=candidates,
                low_precision=low,
                total_hits=total,
            )
        )
    return edges


def verify_edges(edges: list[CanonEdge], chunks: dict[str, Chunk]) -> list[str]:
    """Re-check every candidate against the corpus: the chunk exists, its text
    hashes to the stored hash, and the span contains the phrase. Returns
    problem strings (empty means the index is sound). Cheap enough to run on
    every build - #128 consumes this artifact, so its claims must be checked,
    not asserted."""
    problems: list[str] = []
    for edge in edges:
        at = f"{edge.key.entry_key} {edge.key.book}/{edge.key.chapter}"
        for cand in edge.candidates:
            chunk = chunks.get(cand.chunk_id)
            if chunk is None:
                problems.append(f"{at} {cand.chunk_id}: chunk not in corpus")
                continue
            meta = chunk.metadata
            if edge.key.chapter is None:
                in_pool = meta.book_num == edge.key.book
            elif edge.key.epilogue:
                in_pool = (
                    meta.book_num == EPILOGUE_BOOK
                    and meta.chapter_num == EPILOGUE_CHAPTER
                    and _chunk_ordinal(cand.chunk_id) >= EPILOGUE_FIRST_ORDINAL
                )
            else:
                in_pool = (meta.book_num, meta.chapter_num) == (
                    edge.key.book,
                    edge.key.chapter,
                )
            if not in_pool:
                problems.append(f"{at} {cand.chunk_id}: chunk outside the edge's pool")
                continue
            if chunk_text_hash(chunk.text) != cand.text_hash:
                problems.append(f"{at} {cand.chunk_id}: text hash no longer matches")
                continue
            start, end = cand.span
            fragment = chunk.text[start:end]
            if not _phrase_re(cand.phrase).search(fragment):
                problems.append(f"{at} {cand.chunk_id}: span no longer contains phrase")
    return problems


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
        "total_hits": edge.total_hits,
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
    candidates_total = 0
    total_hit_sum = 0
    for edge in edges:
        by_agreement[edge.agreement] += 1
        by_family[edge.family] += 1
        candidates_total += len(edge.candidates)
        total_hit_sum += edge.total_hits
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
        "candidates_retained": candidates_total,
        "candidates_all_hits": total_hit_sum,
        "low_precision": low_precision,
        "sidebar_only": sidebar_only,
    }


def sample_edges(edges: list[CanonEdge], n: int) -> dict[str, list[CanonEdge]]:
    """Deterministic review sample: exactly min(n, pool) edges spread evenly
    across each agreement class in sorted order (no randomness, no seed).

    The human spot-check (ticket Done-when) runs on this list; `--sample`
    also prints each edge's machine-checkable first-candidate verdict.
    """
    out: dict[str, list[CanonEdge]] = {}
    for agreement in ("both", "forward-only"):
        pool = sorted(
            (e for e in edges if e.agreement == agreement),
            key=lambda e: (e.key.entry_key, e.key.book, e.key.epilogue, e.key.chapter or 0),
        )
        if n <= 0 or not pool:
            out[agreement] = []
            continue
        k = min(n, len(pool))
        picked = [pool[j * len(pool) // k] for j in range(k)]
        out[agreement] = list(dict.fromkeys(picked))  # dedupe, keep order
    return out


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
    "index_chunks",
    "load_entries",
    "resolve_candidates",
    "reverse_edges",
    "sample_edges",
    "summarize",
    "verify_edges",
]
