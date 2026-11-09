"""Author the Charms subject pack from the reviewed authoring batch.

The prose lives in the gitignored
`data/subjects/charms/authoring/charms.json`; this script reconstructs every
quote from the corpus at a hand-picked anchor, hash-checks it through
`validate_pack`, and writes the pack plus a maintainer review sheet. The pack
stays `draft` until the maintainer reviews the prose and marks it reviewed.

  uv run python scripts/author_charms.py
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
    validate_pack,
    write_subject_pack,
)
from app.pipeline.index.builder import load_chunks, text_hash  # noqa: E402

SUBJECT = "charms"
OUT = REPO / "data" / "subjects" / SUBJECT
AUTHORING = OUT / "authoring" / "charms.json"
CITE_RE = re.compile(r"\[(b[1-7]-c\d{2}-\d{4})\]")


def _ascii_form(value: str) -> str:
    """Map curly punctuation to ASCII without changing length."""
    return (
        value.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2014", "-")
        .replace("\u2013", "-")
    )


def _is_sentence_end(text: str, index: int) -> bool:
    """A sentence boundary, excluding initials and dotted abbreviations."""
    if text[index] not in ".!?:":
        return False
    if text[index] != ".":
        return True
    # O.W.L., initials and similar dotted tokens are not sentence ends.
    if index > 0 and text[index - 1].isupper():
        start = index - 1
        while start >= 0 and (text[start].isalnum() or text[start] == "."):
            start -= 1
        token = text[start + 1 : index]
        if len(token) == 1 or "." in token:
            return False
    return True


def quote_for(text: str, needle: str) -> str:
    """Verbatim sentence-shaped slice at `needle`, with a word-window fallback."""
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
    left = s
    while left > 0 and not _is_sentence_end(text, left - 1):
        left -= 1
    while left < s and (text[left].isspace() or text[left] in "\u201d\""):
        left += 1
    right = e
    limit = min(len(text), e + 420)
    while right < limit and not _is_sentence_end(text, right - 1):
        right += 1
    if right < len(text) and text[right] == "\u201d" and _is_sentence_end(text, right - 1):
        right += 1
    if right >= limit and right < len(text) and not text[right].isspace():
        while right > e and not text[right - 1].isspace():
            right -= 1
    candidate = text[left:right]
    if 3 <= len(candidate.split()) <= 90 and len(candidate) <= 480:
        return candidate
    words = list(re.finditer(r"\S+", text))
    hit = next((i for i, w in enumerate(words) if w.start() <= idx < w.end()), 0)
    lo, hi = max(0, hit - 12), min(len(words), hit + 18)
    while hi - lo > 40:
        lo += 1
    return text[words[lo].start() : words[hi - 1].end()]


def _concept(
    concept_id: str,
    spec: dict | None,
    seeds: dict[str, dict],
) -> Concept:
    if spec is not None:
        return Concept(
            concept_id=concept_id,
            subject=SUBJECT,
            kind=spec["kind"],
            title=spec["title"],
            aliases=tuple(spec.get("aliases", ())),
        )
    seed = seeds.get(concept_id)
    if seed is None:
        raise SystemExit(f"no concept spec or seed for {concept_id!r}")
    return Concept(
        concept_id=concept_id,
        subject=SUBJECT,
        kind=seed["kind"],
        title=seed["title"],
        aliases=tuple(seed.get("aliases", ())),
    )


def main() -> int:
    if not AUTHORING.exists():
        raise SystemExit(
            f"authoring prose not found at {AUTHORING}; it is gitignored and "
            "restored from the data backup"
        )
    data = json.loads(AUTHORING.read_text(encoding="utf-8"))
    seeds = {
        s["concept_id"]: s
        for s in (
            json.loads(line)
            for line in (OUT / "seeds.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    chunks = {c.id: c for c in load_chunks(REPO / "data" / "chunks.jsonl")}
    index_hash = text_hash(list(chunks.values()))
    recorded = data.get("index_text_hash")
    if recorded and recorded != index_hash:
        print(
            f"index drift: authoring recorded {recorded}, corpus is {index_hash}",
            file=sys.stderr,
        )
        return 1

    topics = [
        Topic(topic_id=topic_id, subject=SUBJECT, title=title)
        for topic_id, title in sorted(data["topics"].items())
    ]
    concept_specs = data.get("concepts", {})
    concepts: dict[str, Concept] = {}
    materials: dict[str, Material] = {}
    review_rows: list[dict] = []

    for spec in data["materials"]:
        material_id = spec["material_id"]
        text = " ".join(spec["text"].split())
        cited = list(dict.fromkeys(CITE_RE.findall(text)))
        if set(cited) != set(spec["cites"]):
            print(
                f"{material_id}: cite mismatch "
                f"missing={sorted(set(cited) - set(spec['cites']))} "
                f"extra={sorted(set(spec['cites']) - set(cited))}",
                file=sys.stderr,
            )
            return 1
        concept_id = spec["concept"]
        concept = _concept(concept_id, concept_specs.get(concept_id), seeds)
        refs: list[SourceRef] = []
        for chunk_id in cited:
            chunk = chunks.get(chunk_id)
            if chunk is None:
                print(f"{material_id}: chunk {chunk_id} not in corpus", file=sys.stderr)
                return 1
            try:
                quote = quote_for(chunk.text, spec["cites"][chunk_id])
            except ValueError as error:
                print(f"{material_id} {chunk_id}: {error}", file=sys.stderr)
                return 1
            refs.append(
                SourceRef(
                    chunk_id=chunk_id,
                    book=chunk.metadata.book_num,
                    chapter=chunk.metadata.chapter_num,
                    quote=quote,
                    text_hash=chunk_text_hash(chunk.text),
                    index_text_hash=index_hash,
                )
            )
        seed = seeds.get(concept_id, {})
        reference = (
            ReferenceLink(**seed["reference"]) if seed.get("reference") else None
        )
        material = Material(
            material_id=material_id,
            subject=SUBJECT,
            topic=spec["topic"],
            concept=concept_id,
            kind=concept.kind,
            text=text,
            source_refs=refs,
            references=[reference] if reference else [],
            review_status="draft",
        )
        concepts[concept_id] = concept
        materials[material_id] = material
        review_rows.append(
            {"unit": spec.get("unit", ""), "material": material}
        )

    version = data.get("version", "0.1.0")
    pack = SubjectPack(
        manifest=PackManifest(
            subject=SUBJECT,
            tier="owl",
            version=version,
            status="draft",
            built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            index_text_hash=index_hash,
        ),
        topics=sorted(topics, key=lambda topic: topic.topic_id),
        concepts=sorted(concepts.values(), key=lambda concept: concept.concept_id),
        materials=sorted(materials.values(), key=lambda material: material.material_id),
    )

    result = validate_pack(pack, chunks, index_hash)
    print(
        f"validate: ok={result.ok} materials={len(pack.materials)} "
        f"concepts={len(pack.concepts)} topics={len(pack.topics)} "
        f"errors={len(result.errors)} warnings={len(result.warnings)}"
    )
    for error in result.errors:
        print(f"  ERROR {error}")
    for warning in result.warnings:
        print(f"  warn  {warning}")
    if not result.ok:
        return 1

    write_subject_pack(pack, OUT)
    print(f"pack {pack.manifest.version} written to {OUT}")

    lines = [
        "# Charms materials review",
        "",
        f"Pack {pack.manifest.version}, index hash `{index_hash}`. Every",
        "material is `review_status=draft` pending the maintainer's prose",
        "pass. Every quote below was reconstructed from the corpus at a",
        "hand-picked anchor phrase, then hash-checked by `validate_pack`.",
        "",
        "## Coverage",
        "",
        "| Material id | Topic | Concept | Refs |",
        "|---|---|---|---|",
    ]
    for row in review_rows:
        material: Material = row["material"]
        lines.append(
            f"| `{material.material_id}` | `{material.topic}` | "
            f"`{material.concept}` | {len(material.source_refs)} |"
        )
    lines += [
        "",
        f"Pack totals: {len(pack.materials)} materials, "
        f"{len(pack.concepts)} concepts, {len(pack.topics)} topics.",
        "",
        "## Materials",
        "",
    ]
    for row in review_rows:
        material = row["material"]
        lines += [
            f"### `{material.material_id}`",
            "",
            f"Topic `{material.topic}` | concept `{material.concept}` | "
            f"{len(material.source_refs)} refs",
            "",
            material.text,
            "",
        ]
        for ref in material.source_refs:
            quote = " ".join(ref.quote.split())
            quote = quote.replace(" .", ".").replace(" ,", ",")
            lines.append(f"- `{ref.chunk_id}`: \"{quote}\"")
        lines.append("")
    lines += [
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
    ]
    review_path = OUT / "CHARMS_REVIEW.md"
    review_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {review_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
