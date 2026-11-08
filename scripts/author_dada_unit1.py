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
    validate_pack,
    write_subject_pack,
)
from app.pipeline.index.builder import load_chunks  # noqa: E402

INDEX_HASH = "aca4c57462d449f5"
ENTRIES = ("creature/boggart", "magic/boggart-banishing-spell")

UNITS = [
    {
        "material_id": "dada-dark-creatures-boggarts-nature",
        "concept": "dada-creature-boggart",
        "kind": "creature",
        "text": (
            "A boggart is a shape-shifter: it takes the form of whatever it "
            "thinks will frighten us most [b3-c07-0037], and nobody knows "
            "what a boggart looks like when it is alone [b3-c07-0038]. It "
            "favours dark, enclosed spaces - wardrobes, the gap beneath beds, "
            "the cupboards under sinks; one once lodged in a grandfather "
            "clock [b3-c07-0036]. Two consequences for the careful student. "
            "First, the boggart's form is your own fear made visible; it "
            "teaches you about yourself before it teaches you anything else "
            "[b3-c07-0038]. Second, an unseen boggart has not yet chosen "
            "what it will be - the danger is decided at the moment you meet "
            "it [b3-c07-0038]."
        ),
    },
    {
        "material_id": "dada-dark-creatures-boggarts-counter",
        "concept": "dada-magic-boggart-banishing-spell",
        "kind": "spell",
        "text": (
            "The counter is the Banishing Charm, Riddikulus. The word alone "
            "is not enough [b3-c07-0041]: the caster must concentrate on "
            "making the feared form ridiculous - Neville was taught to raise "
            "his wand and picture his grandmother's clothes on his "
            "tormentor, vulture-topped hat and crimson handbag included "
            "[b3-c07-0044], [b3-c07-0045]. Rehearsal order matters. "
            "Professor Lupin drilled the class on the incantation before "
            "wands were raised at all [b3-c07-0041], then one student at a "
            "time faced the wardrobe; when a caster succeeds, the boggart "
            "turns to the next [b3-c07-0045]. Well-executed counters "
            "transform rather than destroy: the professor became a figure in "
            "lace and a towering hat swinging a handbag [b3-c07-0050], the "
            "mummy tangled in its own bandages [b3-c07-0051], the banshee "
            "lost its voice [b3-c07-0052], the hand was caught in a "
            "mousetrap [b3-c07-0054]."
        ),
    },
    {
        "material_id": "dada-dark-creatures-boggarts-field",
        "concept": "dada-creature-boggart",
        "kind": "creature",
        "text": (
            "Field doctrine and failure modes. Freezing is the common "
            "failure: Neville backed away mouthing the word silently while "
            "the shape kept bearing down, and only forced it out at last "
            "[b3-c07-0050]. Precision does not immunise anyone - the "
            "best-prepared student in the year was undone when the boggart "
            "wore the form of a promised failure, and it took time to calm "
            "her [b3-c16-0020]. The charm holds outside the classroom: in "
            "real danger it dispersed a boggart wearing a dementor's shape "
            "into a wisp of smoke [b4-c31-0068], and in the D.A. a boggart "
            "impersonating a dementor served as the fastest road to a "
            "working Patronus - advanced work, noted for the record "
            "[b5-c27-0034]. There is a reason Lupin set a fresh boggart at "
            "the end of the year's practical examination [b3-c16-0018]: the "
            "creature tests recognition, nerve and a clear image under "
            "pressure - which is the whole of defensive practice in one "
            "wardrobe."
        ),
    },
]

CITED = [
    "b3-c07-0036", "b3-c07-0037", "b3-c07-0038", "b3-c07-0041",
    "b3-c07-0044", "b3-c07-0045", "b3-c07-0050", "b3-c07-0051",
    "b3-c07-0052", "b3-c07-0054", "b4-c31-0068", "b3-c16-0018",
    "b3-c16-0020", "b5-c27-0034",
]


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
            index_text_hash=INDEX_HASH,
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

    result = validate_pack(pack, chunks, INDEX_HASH)
    print(f"validate: ok={result.ok} errors={result.errors} "
          f"warnings={result.warnings}")
    if not result.ok:
        return 1
    out = REPO / "data/subjects/dada"
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
        f"- index text hash: {INDEX_HASH}",
        "",
    ]
    (out / "UNIT1_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"review notes: {out / 'UNIT1_REVIEW.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
