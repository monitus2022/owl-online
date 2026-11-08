"""Concept seeding from the canon index x approved lesson tables (#128).

Inputs are structural artifacts: `canon_index.jsonl` (#127, chunk ids, text
hashes, spans, match phrases - never book prose), approved lesson tables
(`config/lessons/*.jsonl`, chapter -> subject + teacher + basis, maintainer
status), the harvester's `entries.jsonl` (url, title, incantation, magic
types) and `fetch_index.jsonl` (access dates for attribution).

Output is a `SeedBundle`: per entry a concept draft (kind guessed from family
and title, incantation as alias), candidate `SourceRef`s with the match phrase
as the quote draft, a `ReferenceLink` carrying title/url/publisher/accessed,
the lesson basis with its precedence and reason, plus loud queues: edges
outside the approved table (unassigned), book-level citations that cannot map
to a chapter (book_level_skipped) and reverse-only agreement kept as hints.

Nothing here decides membership beyond the approved table, and nothing copies
site or book prose: quotes are entry-side match phrases (titles, incantations)
that the corpus itself contains; the builder slices real text at pack-build
time from the recorded spans.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.knowledge.materials import ReferenceLink, SourceRef
from app.knowledge.taxonomy import NOVEL_BOOKS, SUBJECT_KEYS

LEXICON_PUBLISHER = "The Harry Potter Lexicon"
BASIS_PRECEDENCE = (
    "taught-in-class",
    "used-in-exam-context",
    "taxonomy-prior",
    "author-pick",
)
MAX_CHAPTERS = {1: 17, 2: 18, 3: 22, 4: 37, 5: 38, 6: 30, 7: 36}
FAMILIES = frozenset({"magic", "thing", "creature", "place", "event"})
_POTIONISH = re.compile(r"draught|essence|potion|elixir|balm|solution|antidote", re.I)
_UNSAFE_ID = re.compile(r"[^a-z0-9._-]+")


@dataclass(frozen=True)
class LessonRow:
    """One approved chapter -> subject assignment."""

    book: int
    chapter: int
    subject: str
    teacher: str
    basis: str
    reason: str = ""


def load_lesson_table(path: Path) -> tuple[LessonRow, ...]:
    rows = []
    seen: set[tuple[int, int]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        key = (int(r["book"]), int(r["chapter"]))
        if r.get("status") != "approved":
            raise ValueError(f"lesson row {key[0]}-{key[1]} not approved")
        if key in seen:
            raise ValueError(f"duplicate lesson row {key[0]}-{key[1]}")
        seen.add(key)
        if r.get("subject") not in SUBJECT_KEYS:
            raise ValueError(f"lesson row {key[0]}-{key[1]}: unknown subject")
        if key[0] not in NOVEL_BOOKS or key[1] < 1:
            raise ValueError(f"lesson row {key[0]}-{key[1]}: bad chapter")
        if key[1] > MAX_CHAPTERS[key[0]]:
            raise ValueError(f"lesson row {key[0]}-{key[1]}: chapter out of range")
        if r.get("basis") not in BASIS_PRECEDENCE:
            raise ValueError(f"lesson row {key[0]}-{key[1]}: unknown basis")
        teacher = str(r.get("teacher", ""))
        if not teacher.strip():
            raise ValueError(f"lesson row {key[0]}-{key[1]}: blank teacher")
        rows.append(
            LessonRow(
                book=key[0], chapter=key[1],
                subject=str(r["subject"]), teacher=teacher,
                basis=str(r["basis"]), reason=str(r.get("reason", "")),
            )
        )
    return tuple(rows)


def _entry_key_from_url(url: str) -> str | None:
    parts = [p for p in url.split("/") if p]
    if len(parts) < 2:
        return None
    family = next((p for p in parts[:-1] if p in FAMILIES), parts[0])
    return f"{family}/{parts[-1]}"


@dataclass
class ConceptSeed:
    """A draft concept for one entry, with its prefilled evidence."""

    concept_id: str
    subject: str
    kind: str
    title: str
    aliases: tuple[str, ...]
    basis: str
    reason: str
    teacher: str
    agreement: Counter[str] = field(default_factory=Counter)
    source_refs: tuple[SourceRef, ...] = ()
    reference: ReferenceLink | None = None
    chapters: tuple[tuple[int, int], ...] = ()

    def to_row(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "subject": self.subject,
            "kind": self.kind,
            "title": self.title,
            "aliases": list(self.aliases),
            "basis": self.basis,
            "reason": self.reason,
            "teacher": self.teacher,
            "agreement": dict(self.agreement),
            "chapters": [[b, c] for b, c in self.chapters],
            "reference": (
                None if self.reference is None else {
                    "title": self.reference.title,
                    "url": self.reference.url,
                    "publisher": self.reference.publisher,
                    "accessed": self.reference.accessed.isoformat(),
                }
            ),
            "source_refs": [
                {
                    "chunk_id": s.chunk_id, "book": s.book, "chapter": s.chapter,
                    "quote": s.quote, "text_hash": s.text_hash,
                    "index_text_hash": s.index_text_hash,
                    "citation_bucket": s.citation_bucket,
                } for s in self.source_refs
            ],
        }


@dataclass
class SeedBundle:
    subject: str
    concepts: tuple[ConceptSeed, ...]
    unassigned: tuple[dict, ...]
    book_level_skipped: int
    edges_seen: int
    lesson_chapters: int
    disagreement: tuple[dict, ...] = ()
    book_level: tuple[dict, ...] = ()

    def stats(self) -> dict:
        by_kind = Counter(c.kind for c in self.concepts)
        resolved = sum(1 for c in self.concepts if c.source_refs)
        return {
            "subject": self.subject,
            "concepts": len(self.concepts),
            "resolved_with_evidence": resolved,
            "by_kind": dict(by_kind),
            "unassigned": len(self.unassigned),
            "disagreement": len(self.disagreement),
            "book_level": len(self.book_level),
            "book_level_skipped": self.book_level_skipped,
            "edges_seen": self.edges_seen,
            "lesson_chapters": self.lesson_chapters,
        }


def _kind_for(family: str, title: str) -> str:
    if family == "creature":
        return "creature"
    if family == "event":
        return "event"
    if family == "place":
        return "place"
    if family == "magic":
        return "potion" if _POTIONISH.search(title) else "spell"
    return "definition"


def _concept_id(subject: str, entry_key: str) -> str:
    safe = _UNSAFE_ID.sub("-", entry_key.lower()).strip("-")
    return _UNSAFE_ID.sub("-", f"{subject}-{safe}")[:64]


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_seeds(
    subject: str,
    canon_index: Path,
    lesson_table: Path,
    entries: Path,
    fetch_index: Path,
    index_text_hash: str,
) -> SeedBundle:
    table = {
        (row.book, row.chapter): row for row in load_lesson_table(lesson_table)
        if row.subject == subject
    }
    meta: dict[str, dict] = {}
    for e in _load_jsonl(entries):
        key = e.get("entry_key")
        if not key and e.get("family") and e.get("slug"):
            key = f"{e['family']}/{e['slug']}"
        if not key:
            key = _entry_key_from_url(str(e.get("url", "")))
        if key:
            meta[key] = e
    accessed: dict[str, str] = {}
    for f in _load_jsonl(fetch_index):
        url = str(f.get("url", ""))
        stamp = str(f.get("fetched_at", ""))[:10]
        if url and stamp:
            accessed[url] = stamp

    agg: dict[str, dict] = {}
    unassigned_hits: dict[str, dict] = {}
    book_level_rows: list[dict] = []
    disagreement: list[dict] = []
    book_level_skipped = 0
    edges_seen = 0
    for row in _load_jsonl(canon_index):
        edges_seen += 1
        book, chapter = row.get("book"), row.get("chapter")
        key = row["entry_key"]
        if book not in NOVEL_BOOKS:
            continue
        if chapter is None:
            book_level_skipped += 1
            book_level_rows.append({
                "entry_key": key, "title": row.get("title", ""),
                "book": book, "agreement": row.get("agreement", "?"),
                "candidates": len(row.get("candidates", ())),
            })
            continue
        lesson = table.get((book, chapter))
        if lesson is None:
            u = unassigned_hits.setdefault(
                key, {"entry_key": key, "title": row.get("title", ""),
                      "verified": 0, "chapters": set()}
            )
            u["verified"] += 1 if row.get("candidates") else 0
            u["chapters"].add((book, chapter))
            continue

        a = agg.setdefault(key, {
            "family": row.get("family", "thing"), "title": row.get("title", ""),
            "agreement": Counter(), "refs": [], "chapters": set(),
            "bases": [],
        })
        a["agreement"][row.get("agreement", "?")] += 1
        a["chapters"].add((book, chapter))
        a["bases"].append(lesson)
        for cand in row.get("candidates", ()):
            # The #127 resolver writes books-bucket candidates only. Carry the
            # bucket when present so an upstream change cannot silently widen
            # the pack's source policy; absent means the resolver's books-only
            # default.
            ref = SourceRef(
                chunk_id=cand["chunk_id"], book=book, chapter=chapter,
                quote=cand["phrase"], text_hash=cand["text_hash"],
                index_text_hash=index_text_hash,
                citation_bucket=cand.get("bucket", "books"),
            )
            a["refs"].append(ref)

    concepts = []
    for key, a in sorted(agg.items()):
        if set(a["agreement"]) - {"both"}:
            disagreement.append({
                "entry_key": key, "title": a["title"],
                "agreement": dict(a["agreement"]),
                "chapters": sorted(a["chapters"]),
            })
        lesson_best = min(
            a["bases"], key=lambda r: BASIS_PRECEDENCE.index(r.basis)
            if r.basis in BASIS_PRECEDENCE else 99
        )
        m = meta.get(key, {})
        inc = str(m.get("incantation", "")).strip()
        aliases = ((inc,) if inc and inc.lower() != a["title"].lower() else ())
        url = str(m.get("url", ""))
        stamp = accessed.get(url)
        reference = (
            ReferenceLink(
                title=a["title"], url=url, publisher=LEXICON_PUBLISHER,
                accessed=date.fromisoformat(stamp),
            )
            if url and stamp else None
        )
        concepts.append(ConceptSeed(
            concept_id=_concept_id(subject, key), subject=subject,
            kind=_kind_for(a["family"], a["title"]), title=a["title"],
            aliases=aliases, basis=lesson_best.basis, reason=lesson_best.reason,
            teacher=lesson_best.teacher, agreement=a["agreement"],
            source_refs=tuple(
                {r.chunk_id: r for r in a["refs"]}.values()
            ),
            reference=reference,
            chapters=tuple(sorted(a["chapters"])),
        ))

    unassigned = tuple(
        {"entry_key": v["entry_key"], "title": v["title"],
         "verified": v["verified"],
         "chapters": sorted(v["chapters"])}
        for v in sorted(unassigned_hits.values(),
                        key=lambda v: (-v["verified"], v["entry_key"]))
    )

    return SeedBundle(
        subject=subject, concepts=tuple(concepts), unassigned=unassigned,
        book_level_skipped=book_level_skipped, edges_seen=edges_seen,
        lesson_chapters=len(table), disagreement=tuple(disagreement),
        book_level=tuple(book_level_rows),
    )


def write_bundle(bundle: SeedBundle, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "seeds.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for seed in bundle.concepts:
            handle.write(json.dumps(seed.to_row(), ensure_ascii=False) + "\n")
    queue_path = out_dir / "queue_unassigned.jsonl"
    with queue_path.open("w", encoding="utf-8") as handle:
        for row in bundle.unassigned:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    for name, rows in (
        ("queue_disagreement.jsonl", bundle.disagreement),
        ("queue_book_level.jsonl", bundle.book_level),
    ):
        with (out_dir / name).open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "unassigned": len(bundle.unassigned),
        "disagreement": len(bundle.disagreement),
        "book_level": len(bundle.book_level),
        "edges_seen": bundle.edges_seen,
    }
    (out_dir / "queue_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return path
