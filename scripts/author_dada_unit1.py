"""Author DADA Unit 1 (Boggarts and the Banishing Spell) as a pack material.

Sample for maintainer review (#87/#128). The material text is Ashcombe's own
prose; every claim carries an inline [chunk-id] and a matching SourceRef
built from the resolver's verified candidates (hash + span already checked
against the corpus). Review notes with the full passages land in the pack
directory (gitignored; backed up via the owl-data bundle).

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
    validate_pack,
    write_subject_pack,
)
from app.pipeline.index.builder import load_chunks  # noqa: E402

INDEX_HASH = "aca4c57462d449f5"

TEXT = (
    "Boggarts favour dark, enclosed spaces: wardrobes, the gap beneath beds, "
    "the cupboards under sinks [b3-c07-0036]. They are shape-shifters, taking "
    "the form of whatever they think will frighten us most [b3-c07-0037], and "
    "nobody knows what a boggart looks like when it is alone [b3-c07-0038] - "
    "so the boggart teaches us about ourselves before it teaches us anything "
    "else. The counter is the Banishing Charm, Riddikulus. The word alone is "
    "not enough [b3-c07-0041]: you must picture the joke first, as Neville "
    "did, dressing his tormentor in grandmother's vulture-topped hat and "
    "handbag [b3-c07-0044], [b3-c07-0045]. We practise the word without wands, "
    "then face the wardrobe one student at a time, wand raised; when one "
    "succeeds, the boggart turns to the next [b3-c07-0050], [b3-c07-0051], "
    "[b3-c07-0052], [b3-c07-0054]. Two warnings. Freezing is the common "
    "failure: mouth the word silently and the shape keeps bearing down "
    "[b3-c07-0050]. And the classroom is only rehearsal - the charm held in "
    "real danger, dispelling a boggart wearing a dementor's shape "
    "[b4-c31-0068], and even the most precise student can be undone when the "
    "fear is a promised failure [b3-c16-0020]. The D.A. later used a boggart "
    "as the fastest road to a Patronus [b5-c27-0034]; treat that as advanced "
    "work, not the unit. A boggart closed Professor Lupin's practical "
    "examinations for good reason [b3-c16-0018]: it tests everything this "
    "unit is - recognition, nerve, and a clear image under pressure."
)

CITED = [
    "b3-c07-0036", "b3-c07-0037", "b3-c07-0038", "b3-c07-0041",
    "b3-c07-0044", "b3-c07-0045", "b3-c07-0050", "b3-c07-0051",
    "b3-c07-0052", "b3-c07-0054", "b4-c31-0068", "b3-c16-0018",
    "b3-c16-0020", "b5-c27-0034",
]


def widen(text: str, start: int, end: int) -> str:
    """Grow the recorded span to a whole-word quote of at least three words."""
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
    return text[s:e]


def main() -> int:
    spans: dict[str, tuple[int, int]] = {}
    for line in (REPO / "data/lexicon/canon_index.jsonl").read_text(
            encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["entry_key"] in ("creature/boggart", "magic/boggart-banishing-spell"):
            for c in e.get("candidates", ()):
                prev = spans.get(c["chunk_id"])
                if prev is None or (c["span"][1] - c["span"][0]) > (prev[1] - prev[0]):
                    spans[c["chunk_id"]] = tuple(c["span"])
    chunks = {c.id: c for c in load_chunks(REPO / "data/chunks.jsonl")}
    CHUNK_TEXTS = {cid: chunks[cid].text for cid in CITED if cid in chunks}

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
    missing = [c for c in CITED if c not in by_chunk]
    if missing:
        print(f"cited chunks with no seeded ref: {missing}", file=sys.stderr)
        return 1
    refs = []
    for cid in CITED:
        seed = by_chunk[cid]
        # quote is reconstructed from the corpus at the recorded span (the
        # #127 contract), widened to whole words; never the lowercase match
        # phrase, which is not verbatim and trips the pack quote rule.
        text = CHUNK_TEXTS[cid]
        span = spans.get(cid)
        if span is None:
            print(f"no span for {cid}", file=sys.stderr)
            return 1
        quote = widen(text, span[0], span[1])
        refs.append(SourceRef(
            chunk_id=cid, book=seed["book"], chapter=seed["chapter"],
            quote=quote, text_hash=seed["text_hash"],
            index_text_hash=seed["index_text_hash"],
        ))
    refs = tuple(refs)

    references = [
        ReferenceLink(**boggart["reference"]),
        ReferenceLink(**spell["reference"]),
    ]

    material = Material(
        material_id="dada-dark-creatures-boggarts-001",
        subject="dada",
        topic="dark-creatures",
        concept="dada-creature-boggart",
        kind="creature",
        text=TEXT,
        source_refs=list(refs),
        references=references,
        review_status="draft",
    )
    pack = SubjectPack(
        manifest=PackManifest(
            subject="dada", tier="owl", version="0.1.0", status="draft",
            built_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            index_text_hash=INDEX_HASH,
        ),
        topics=[Topic(topic_id="dark-creatures", subject="dada",
                      title="Dark Creatures")],
        concepts=[Concept(**{k: v for k, v in boggart.items()
                             if k in ("concept_id", "subject", "kind",
                                      "title", "aliases")})],
        materials=[material],
    )

    result = validate_pack(pack, chunks, INDEX_HASH)
    print(f"validate: ok={result.ok} errors={result.errors} "
          f"warnings={result.warnings}")
    if not result.ok:
        return 1
    out = REPO / "data/subjects/dada"
    write_subject_pack(pack, out)
    print(f"pack written to {out}")

    lines = [
        "# Unit 1 review: Boggarts and the Banishing Spell",
        "",
        "Material: `dada-dark-creatures-boggarts-001` (kind creature,",
        "concept boggart; review_status draft). The spell concept",
        "(`dada-magic-boggart-banishing-spell`, alias Riddikulus) is cited",
        "inside the unit; the single-concept material schema keeps it out of",
        "`concepts.jsonl` for now - a known schema question to settle before",
        "the remaining units (option: one material per concept, or a",
        "`concepts` list on Material).",
        "",
        "## Text",
        "",
        TEXT,
        "",
        "## Evidence passages (what each cited chunk actually says)",
        "",
    ]
    for cid in CITED:
        for ref in material.source_refs:
            if ref.chunk_id == cid:
                q = " ".join(ref.quote.split())
                lines.append(f"- `{cid}`: \"{q[:200]}\"")
                break
    lines += [
        "",
        "## References (attribution only, never load-bearing)",
        "",
    ]
    for r in references:
        lines.append(f"- {r.title} - {r.url} ({r.publisher}, accessed "
                     f"{r.accessed})")
    lines += [
        "",
        "## Checks",
        "",
        f"- validate_pack: ok={result.ok}, {len(refs)} source refs, every "
        "text hash recomputed against the corpus, every quote present, every "
        "book/chapter matched to chunk metadata",
        f"- index text hash: {INDEX_HASH}",
        "",
    ]
    (out / "UNIT1_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {out / 'UNIT1_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
