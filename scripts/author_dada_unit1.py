"""Author DADA Unit 1 (Boggarts and the Banishing Spell) as a material batch.

Maintainer decisions 2026-11-08: materials are batched generously (several per
unit, one centre each) and lesson mode assembles from them (see LESSON note in
the review sheet). The material texts are Ashcombe's own prose; every claim
carries an inline [chunk-id] with a matching SourceRef whose quote is
reconstructed verbatim from the corpus at the resolver's recorded span.

  uv run python scripts/author_dada_unit1.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.knowledge.materials import Material, ReferenceLink, SourceRef  # noqa: E402
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

AUTHORING = REPO / "data" / "subjects" / "dada" / "authoring" / "unit1.json"


def _load_authoring() -> dict:
    if not AUTHORING.exists():
        raise SystemExit(
            f"authoring prose not found at {AUTHORING}; it is gitignored and "
            "restored from the owl-data backup"
        )
    return json.loads(AUTHORING.read_text(encoding="utf-8"))


_AUTHORING = _load_authoring()
UNITS: list[dict] = _AUTHORING["materials"]
CITED: list[str] = _AUTHORING["cited"]

ENTRIES = ("creature/boggart", "magic/boggart-banishing-spell")

def widen(text: str, start: int, end: int) -> str:
    """Whole-word, sentence-shaped verbatim slice around the recorded span."""
    n = len(text)
    s, e = max(0, min(start, n)), max(0, min(end, n))
    while s > 0 and not text[s - 1].isspace():
        s -= 1
    while e < n and not text[e].isspace():
        e += 1
    while len(text[s:e].split()) < 3:
        before = (s, e)
        if s > 0:
            j = text.rfind(" ", 0, s)
            s = 0 if j < 0 else j + 1
        if len(text[s:e].split()) < 3 and e < n:
            k = text.find(" ", e)
            e = n if k < 0 else k + 1
        if (s, e) == before:
            break
    sent_end = {".", "!", "?", ":", "”"}
    left = s
    while left > 0 and text[left - 1] not in sent_end:
        left -= 1
    while left < s and text[left].isspace():
        left += 1
    right = e
    limit = min(n, e + 180)
    while right < limit and text[right - 1] not in sent_end:
        right += 1
    while right > e and text[right - 1].isspace():
        right -= 1
    candidate = text[left:right]
    if 3 <= len(candidate.split()) <= 60 and len(candidate) <= 260:
        return candidate
    return text[s:e]


def main() -> int:
    spans: dict[str, tuple[int, int]] = {}
    for line in (REPO / "data/lexicon/canon_index.jsonl").read_text(
            encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["entry_key"] in ENTRIES:
            for c in e.get("candidates", ()):
                prev = spans.get(c["chunk_id"])
                if prev is None or (c["span"][1] - c["span"][0]) > (prev[1] - prev[0]):
                    spans[c["chunk_id"]] = tuple(c["span"])

    chunks = {c.id: c for c in load_chunks(REPO / "data/chunks.jsonl")}
    index_hash = text_hash(list(chunks.values()))
    recorded = _AUTHORING.get("index_text_hash")
    if recorded and recorded != index_hash:
        print(
            f"index drift: authoring recorded {recorded}, corpus is {index_hash}",
            file=sys.stderr,
        )
        return 1
    seeds = {}
    for line in (REPO / "data/subjects/dada/seeds.jsonl").read_text(
            encoding="utf-8").splitlines():
        s = json.loads(line)
        seeds[s["concept_id"]] = s
    boggart = seeds["dada-creature-boggart"]
    spell = seeds["dada-magic-boggart-banishing-spell"]

    by_chunk: dict[str, dict] = {}
    for src in list(boggart["source_refs"]) + list(spell["source_refs"]):
        by_chunk.setdefault(src["chunk_id"], src)
    missing = [c for c in CITED if c not in by_chunk or c not in chunks]
    if missing:
        print(f"cited chunks missing from seeds/corpus: {missing}", file=sys.stderr)
        return 1

    all_refs = []
    for cid in CITED:
        seed = by_chunk[cid]
        quote = widen(chunks[cid].text, *spans[cid])
        all_refs.append(SourceRef(
            chunk_id=cid, book=seed["book"], chapter=seed["chapter"],
            quote=quote, text_hash=seed["text_hash"],
            index_text_hash=seed["index_text_hash"],
        ))
    refs_by_id = {r.chunk_id: r for r in all_refs}
    references = [ReferenceLink(**boggart["reference"]),
                  ReferenceLink(**spell["reference"])]

    materials = []
    for u in UNITS:
        cited = [c for c in CITED if f"[{c}]" in u["text"]]
        materials.append(Material(
            material_id=u["material_id"], subject="dada",
            topic="dark-creatures", concept=u["concept"], kind=u["kind"],
            text=u["text"], source_refs=[refs_by_id[c] for c in cited],
            references=list(references), review_status="draft",
        ))

    pack = SubjectPack(
        manifest=PackManifest(
            subject="dada", tier="owl", version="0.2.0", status="draft",
            built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            index_text_hash=index_hash,
        ),
        topics=[Topic(topic_id="dark-creatures", subject="dada",
                      title="Dark Creatures")],
        concepts=[
            Concept(**{k: v for k, v in boggart.items()
                       if k in ("concept_id", "subject", "kind", "title",
                                "aliases")}),
            Concept(**{k: v for k, v in spell.items()
                       if k in ("concept_id", "subject", "kind", "title",
                                "aliases")}),
        ],
        materials=materials,
    )

    result = validate_pack(pack, chunks, index_hash)
    print(f"validate: ok={result.ok} errors={result.errors} "
          f"warnings={result.warnings}")
    if not result.ok:
        return 1
    out = REPO / "data/subjects/dada"
    if (out / "pack.toml").exists():
        existing = load_subject_pack(out)
        if existing.manifest.status == "published" and "--force" not in sys.argv:
            print(
                f"{out} holds a published pack; pass --force to rebuild it as a draft",
                file=sys.stderr,
            )
            return 1
    write_subject_pack(pack, out)
    print(f"pack written to {out}")

    lines = [
        "# Unit 1 review: Boggarts and the Banishing Spell (material batch)",
        "",
        "Three materials, one centre each - nature / counter / field.",
        "Both concepts (creature and spell, alias Riddikulus) are now real",
        "pack concepts, each with its own material - the batching decision",
        "resolved the single-concept constraint without a schema change.",
        "",
        "## Materials",
        "",
    ]
    for m in materials:
        lines.append(f"### {m.material_id}")
        lines.append(f"concept: `{m.concept}` | {len(m.source_refs)} refs")
        lines.append("")
        lines.append(m.text)
        lines.append("")
    lines += [
        "## Evidence passages (verbatim corpus quotes, all hash-checked)",
        "",
    ]
    for r in all_refs:
        q = " ".join(r.quote.split())
        lines.append(f"- `{r.chunk_id}`: \"{q[:200]}\"")
    lines += [
        "",
        "## References (attribution only, never load-bearing)",
        "",
    ]
    for ref in references:
        lines.append(f"- {ref.title} - {ref.url} ({ref.publisher}, accessed "
                     f"{ref.accessed})")
    lines += [
        "",
        "## From materials to a lesson (#43 preview)",
        "",
        "A lesson adds no new facts; it assembles reviewed materials in a",
        "teaching order with connectors in the professor's register. Unit 1",
        "assembles as:",
        "",
        "1. Hook - why boggarts matter to an Auror-track student: nature",
        "   material, opening lines cited [mat:dada-dark-creatures-",
        "boggarts-nature].",
        "2. Mechanism - the fear-shape and the unknown true form (nature,",
        "   section 2).",
        "3. Counter - word, then image, then wand; rehearsal order (counter",
        "   material).",
        "4. Guided practice - the class rotation becomes the practice intent",
        "   against the same material context (a bespoke question: 'what does",
        "   Riddikulus require that other charms do not?').",
        "5. Failure cases and cautions - freezing, precision-not-immunity",
        "   (field material).",
        "6. Why it is examined - Lupin's practical as closing rationale",
        "   (field material) - stated as canon history, never as a promise",
        "   about Ashcombe's own examination format (non-disclosure holds).",
        "7. Reflection + further reading - the two attributed Lexicon",
        "   references.",
        "",
        "Every section cites a material id and through it its chunk refs -",
        "the same rule as exam questions. v1 lessons can be assembled",
        "offline and deterministically from this map; #43 runtime only adds",
        "connective voice and answers follow-up questions.",
        "",
        "## Checks",
        "",
        f"- validate_pack: ok={result.ok}; every text hash recomputed against",
        "  the corpus; every quote verbatim; book/chapter matched to chunk",
        f"- index text hash: {index_hash}",
        "",
    ]
    (out / "UNIT1_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {out / 'UNIT1_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
