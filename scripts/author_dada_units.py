"""Author DADA Units 2-8 as a material batch (appends to the Unit 1 pack).

Every claim in the prose was written only after reading the cited chunk. The
`cites` entries carry a short anchor phrase that occurs in that chunk; the
script slices the corpus there, widens to a whole sentence or a sane word
window, and stores the verbatim quote. The pack validator then recomputes the
chunk hashes and checks every quote is a real substring, so a drifted or
invented quotation fails the build.

  uv run python scripts/author_dada_units.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.materials import (  # noqa: E402
    Material,
    ReferenceLink,
    SourceRef,
    chunk_text_hash,
)
from app.knowledge.packs import (  # noqa: E402
    Concept,
    PackManifest,
    SubjectPack,
    Topic,
    load_subject_pack,
    validate_pack,
    write_subject_pack,
)
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

VERSION = "0.3.0"
CITE_RE = re.compile(r"\[(b[1-7]-c\d{2}-\d{4})\]")

AUTHORING = REPO / "data" / "subjects" / "dada" / "authoring" / "units2_8.json"


def _load_authoring() -> dict:
    if not AUTHORING.exists():
        raise SystemExit(
            f"authoring prose not found at {AUTHORING}; it is gitignored and "
            "restored from the owl-data backup"
        )
    return json.loads(AUTHORING.read_text(encoding="utf-8"))


_AUTHORING = _load_authoring()
MATERIALS: list[dict] = _AUTHORING["materials"]
LESSON_MAP: dict[int, list[str]] = {
    int(key): value for key, value in _AUTHORING["lesson_map"].items()
}
VERSION = _AUTHORING.get("version", "0.3.0")


TOPICS = {
    "dark-creatures": "Dark Creatures",
    "dark-arts": "The Dark Arts",
    "defensive-magic": "Defensive Magic",
    "dueling": "Dueling",
}

def _ascii_form(value: str) -> str:
    """Map curly punctuation to ASCII without changing length, so match
    indices still address the raw chunk text."""
    return (
        value.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )


def quote_for(text: str, needle: str) -> str:
    """Verbatim whole-sentence slice at `needle`, with a word-window fallback."""
    pattern = re.compile(
        r"\s+".join(re.escape(word) for word in _ascii_form(needle).split()),
        re.IGNORECASE,
    )
    match = pattern.search(_ascii_form(text))
    if match is None:
        raise ValueError(f"anchor not found: {needle!r}")
    idx, end = match.start(), match.end()
    s, e = idx, end
    while s > 0 and not text[s - 1].isspace():
        s -= 1
    while e < len(text) and not text[e].isspace():
        e += 1
    sent_end = {".", "!", "?", ":"}
    left = s
    while left > 0 and text[left - 1] not in sent_end:
        left -= 1
    while left < s and (text[left].isspace() or text[left] in "\u201d\""):
        left += 1
    right = e
    limit = min(len(text), e + 420)
    while right < limit and text[right - 1] not in sent_end:
        right += 1
    if right < len(text) and text[right] == "\u201d" and text[right - 1] in sent_end:
        right += 1
    if right >= limit and right < len(text) and not text[right].isspace():
        while right > e and not text[right - 1].isspace():
            right -= 1
    candidate = text[left:right]
    if 3 <= len(candidate.split()) <= 90 and len(candidate) <= 480:
        return candidate
    # Long sentence: take a centred word window, still a verbatim substring.
    words = list(re.finditer(r"\S+", text))
    hit = next((i for i, w in enumerate(words) if w.start() <= idx < w.end()), 0)
    lo, hi = max(0, hit - 12), min(len(words), hit + 18)
    while hi - lo > 40:
        lo += 1
    return text[words[lo].start():words[hi - 1].end()]


def concept_from_seed(seed: dict) -> Concept:
    aliases = tuple(a for a in seed.get("aliases", ()) if a.lower() != "various")
    return Concept(
        concept_id=seed["concept_id"],
        subject=seed["subject"],
        kind=seed["kind"],
        title=seed["title"],
        aliases=aliases,
    )


def reference_from_seed(seed: dict) -> ReferenceLink | None:
    ref = seed.get("reference")
    return ReferenceLink(**ref) if ref else None


def main() -> int:
    out = REPO / "data/subjects/dada"
    if not (out / "pack.toml").exists():
        print(f"no pack at {out}; run the Unit 1 authoring script first", file=sys.stderr)
        return 1
    pack = load_subject_pack(out)
    if pack.manifest.status == "published" and "--force" not in sys.argv:
        print(
            f"{out} holds a published pack; pass --force to rebuild it as a draft",
            file=sys.stderr,
        )
        return 1
    seeds = {
        s["concept_id"]: s
        for s in (
            json.loads(line)
            for line in (out / "seeds.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    chunks = {c.id: c for c in load_chunks(REPO / "data/chunks.jsonl")}
    index_hash = text_hash(list(chunks.values()))
    recorded = _AUTHORING.get("index_text_hash")
    if recorded and recorded != index_hash:
        print(
            f"index drift: authoring recorded {recorded}, corpus is {index_hash}",
            file=sys.stderr,
        )
        return 1

    topics = {t.topic_id: t for t in pack.topics}
    for topic_id, title in TOPICS.items():
        topics.setdefault(
            topic_id, Topic(topic_id=topic_id, subject="dada", title=title)
        )
    concepts = {c.concept_id: c for c in pack.concepts}
    materials = {m.material_id: m for m in pack.materials}

    review_rows: list[dict] = []

    for spec in MATERIALS:
        text = " ".join(spec["text"].split())
        cited = CITE_RE.findall(text)
        if len(cited) != len(set(cited)):
            # A repeat is allowed in prose, but the ref list is deduped.
            cited = list(dict.fromkeys(cited))
        missing = [c for c in cited if c not in spec["cites"]]
        extra = [c for c in spec["cites"] if c not in cited]
        if missing or extra:
            print(
                f"{spec['material_id']}: cite mismatch missing={missing} extra={extra}",
                file=sys.stderr,
            )
            return 1
        seed = seeds[spec["concept"]]
        refs = []
        for cid in cited:
            chunk = chunks.get(cid)
            if chunk is None:
                print(f"{spec['material_id']}: chunk {cid} not in corpus", file=sys.stderr)
                return 1
            try:
                quote = quote_for(chunk.text, spec["cites"][cid])
            except ValueError as exc:
                print(f"{spec['material_id']} {cid}: {exc}", file=sys.stderr)
                return 1
            refs.append(
                SourceRef(
                    chunk_id=cid,
                    book=chunk.metadata.book_num,
                    chapter=chunk.metadata.chapter_num,
                    quote=quote,
                    text_hash=chunk_text_hash(chunk.text),
                    index_text_hash=index_hash,
                )
            )
        reference = reference_from_seed(seed)
        materials[spec["material_id"]] = Material(
            material_id=spec["material_id"],
            subject="dada",
            topic=spec["topic"],
            concept=spec["concept"],
            kind=seed["kind"],
            text=text,
            source_refs=refs,
            references=[reference] if reference else [],
            review_status="draft",
        )
        concepts[spec["concept"]] = concept_from_seed(seed)
        review_rows.append(
            {
                "unit": spec["unit"],
                "material_id": spec["material_id"],
                "material": materials[spec["material_id"]],
            }
        )

    pack = SubjectPack(
        manifest=PackManifest(
            subject="dada",
            tier="owl",
            version=VERSION,
            status="draft",
            built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            index_text_hash=index_hash,
        ),
        topics=sorted(topics.values(), key=lambda t: t.topic_id),
        concepts=sorted(concepts.values(), key=lambda c: c.concept_id),
        materials=sorted(materials.values(), key=lambda m: m.material_id),
    )

    result = validate_pack(pack, chunks, index_hash)
    print(
        f"validate: ok={result.ok} materials={len(pack.materials)} "
        f"concepts={len(pack.concepts)} errors={len(result.errors)} "
        f"warnings={len(result.warnings)}"
    )
    for err in result.errors[:20]:
        print(f"  ERROR {err}")
    for warn in result.warnings:
        print(f"  warn  {warn}")
    if not result.ok:
        return 1

    write_subject_pack(pack, out)
    print(f"pack {pack.manifest.version} written to {out}")

    lines = [
        "# DADA materials review: Units 2-8",
        "",
        f"Pack {pack.manifest.version}, index hash `{index_hash}`. Every",
        "material is `review_status=draft` pending the maintainer's prose",
        "pass. Every quote below was reconstructed from the corpus at a",
        "hand-picked anchor phrase, then hash-checked by `validate_pack`.",
        "",
        "## Coverage",
        "",
        "| Unit | Materials | Concept | Refs |",
        "|---|---|---|---|",
    ]
    for row in review_rows:
        m = row["material"]
        lines.append(
            f"| {row['unit']} | `{m.material_id}` | `{m.concept}` | "
            f"{len(m.source_refs)} |"
        )
    lines += ["", f"Pack totals: {len(pack.materials)} materials, "
              f"{len(pack.concepts)} concepts, "
              f"{len(pack.topics)} topics.", ""]

    for unit in range(2, 9):
        rows = [r for r in review_rows if r["unit"] == unit]
        lines += [f"## Unit {unit}", ""]
        for row in rows:
            m: Material = row["material"]
            lines += [
                f"### `{m.material_id}`",
                "",
                f"Topic `{m.topic}` | concept `{m.concept}` | {len(m.source_refs)} refs",
                "",
                m.text,
                "",
            ]
            for ref in m.source_refs:
                q = " ".join(ref.quote.split())
                q = q.replace(" .", ".").replace(" ,", ",")
                lines.append(f"- `{ref.chunk_id}`: \"{q}\"")
            lines.append("")
        lines += ["Lesson assembly:", ""]
        for step in LESSON_MAP[unit]:
            lines.append(f"- {step}")
        lines.append("")

    lines += ["## References (attribution only, never load-bearing)", ""]
    seen_refs: set[str] = set()
    for row in review_rows:
        for ref in row["material"].references:
            if ref.url in seen_refs:
                continue
            seen_refs.add(ref.url)
            lines.append(
                f"- {ref.title} - {ref.url} ({ref.publisher}, accessed {ref.accessed})"
            )
    lines += [
        "",
        "## Checks",
        "",
        f"- `validate_pack`: ok={result.ok}; "
        f"{len(pack.materials)} materials, {len(pack.concepts)} concepts",
        "- every chunk text hash recomputed against the corpus",
        "- every quote a verbatim substring of its chunk",
        "- every ref book/chapter matched to chunk metadata",
        f"- index text hash `{index_hash}`",
        f"- warnings: {len(result.warnings)} (all `review_status=draft`)",
        "",
        "## Gaps found while authoring",
        "",
        "- Werewolf restraint needs `b3 c18` (Wolfsbane and the full moon)",
        "  and `b5 c22` (the bite has no cure); neither is an approved row.",
        "  Unit 4 therefore covers recognition, law and fear, not containment.",
        "- The Unbreakable Vow's explanation is in `b6 c02`, not the approved",
        "  `b6 c15`; Unit 5 does not make a claim the approved row cannot carry.",
        "- The b6 c09 strike candidate is overturned: `b6-c09-0029` is Snape's",
        "  defence doctrine and `b6-c09-0036` is a Shield Charm, both DADA.",
        "- The b6 rows' shared reason (\"Dumbledore's Army practical chapters\")",
        "  is wrong for book 6; relabel when the table is next touched.",
        "",
    ]
    (out / "UNITS_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {out / 'UNITS_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
