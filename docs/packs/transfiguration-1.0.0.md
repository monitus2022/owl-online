# Transfiguration subject pack 1.0.0

- Date: 2026-11-10
- Subject: `transfiguration`
- Version: `1.0.0`
- Status: `published`
- Fingerprint: `81c6cd2c91cb975f`
- Index text hash: `aca4c57462d449f5`
- Materials: 34
- Concepts: 29
- Topics: 6
- Source refs: 76
- Reviewed materials: 34/34

## Validation

```text
validate_pack: ok=True errors=0 warnings=0
materials=34 concepts=29 topics=6
fingerprint=81c6cd2c91cb975f
```

The pack directory is gitignored. This record is structure-only and
contains no corpus text; the material prose stays in the local pack and
the data backup.

## Topic coverage

| Topic | Materials |
|---|---:|
| `transfiguration-creatures` | 5 |
| `transfiguration-foundations` | 5 |
| `transfiguration-objects` | 6 |
| `transfiguration-reversal` | 5 |
| `transfiguration-self` | 7 |
| `transfiguration-vanishing` | 6 |

## Kind mix

| Kind | Materials |
|---|---:|
| `definition` | 14 |
| `procedure` | 12 |
| `spell` | 8 |

## Materials

| Material id | Topic | Concept | Refs |
|---|---|---|---:|
| `transfiguration-conjuring` | `transfiguration-vanishing` | `transfiguration-conjuring` | 4 |
| `transfiguration-conjuring-limits` | `transfiguration-vanishing` | `transfiguration-conjuring-limits` | 2 |
| `transfiguration-creature-animation` | `transfiguration-creatures` | `transfiguration-animation` | 2 |
| `transfiguration-creature-conjured-creatures` | `transfiguration-creatures` | `transfiguration-conjured-creatures` | 2 |
| `transfiguration-creature-cross-species-switching` | `transfiguration-creatures` | `transfiguration-cross-species-switching` | 2 |
| `transfiguration-creature-scale-limit` | `transfiguration-creatures` | `transfiguration-scale-limit` | 1 |
| `transfiguration-creature-trans-species-theory` | `transfiguration-creatures` | `transfiguration-trans-species-transformation` | 2 |
| `transfiguration-evanesco` | `transfiguration-vanishing` | `transfiguration-evanesco` | 2 |
| `transfiguration-foundation-concentration` | `transfiguration-foundations` | `transfiguration-concentration` | 2 |
| `transfiguration-foundation-definition` | `transfiguration-foundations` | `transfiguration-definition` | 3 |
| `transfiguration-foundation-gamps-law` | `transfiguration-foundations` | `transfiguration-gamps-law` | 2 |
| `transfiguration-foundation-practice` | `transfiguration-foundations` | `transfiguration-practice` | 2 |
| `transfiguration-foundation-theory` | `transfiguration-foundations` | `transfiguration-theory` | 3 |
| `transfiguration-inanimatus-conjurus` | `transfiguration-vanishing` | `transfiguration-inanimatus-conjurus` | 2 |
| `transfiguration-object-inanimate` | `transfiguration-objects` | `transfiguration-inanimate-objects` | 2 |
| `transfiguration-object-match-to-needle` | `transfiguration-objects` | `transfiguration-match-to-needle` | 2 |
| `transfiguration-object-mouse-to-snuffbox` | `transfiguration-objects` | `transfiguration-mouse-to-snuffbox` | 2 |
| `transfiguration-object-switching-spell` | `transfiguration-objects` | `transfiguration-switching-spell` | 3 |
| `transfiguration-object-teapot-to-tortoise` | `transfiguration-objects` | `transfiguration-teapot-to-tortoise` | 2 |
| `transfiguration-object-to-animal` | `transfiguration-objects` | `transfiguration-object-to-animal` | 2 |
| `transfiguration-reversal-accidental` | `transfiguration-reversal` | `transfiguration-accidental-transfiguration` | 3 |
| `transfiguration-reversal-partial` | `transfiguration-reversal` | `transfiguration-partial-transfiguration` | 3 |
| `transfiguration-reversal-restorative` | `transfiguration-reversal` | `transfiguration-untransfiguration` | 2 |
| `transfiguration-reversal-self` | `transfiguration-reversal` | `transfiguration-reversal-self` | 2 |
| `transfiguration-reversal-untransfiguration` | `transfiguration-reversal` | `transfiguration-untransfiguration` | 2 |
| `transfiguration-self-animagus` | `transfiguration-self` | `transfiguration-animagus` | 2 |
| `transfiguration-self-animagus-register` | `transfiguration-self` | `transfiguration-animagus` | 4 |
| `transfiguration-self-animagus-risk` | `transfiguration-self` | `transfiguration-animagus` | 2 |
| `transfiguration-self-animagus-vs-metamorphmagus` | `transfiguration-self` | `transfiguration-animagus-vs-metamorphmagus` | 2 |
| `transfiguration-self-human-transfiguration` | `transfiguration-self` | `transfiguration-human-transfiguration` | 2 |
| `transfiguration-self-metamorphmagus` | `transfiguration-self` | `transfiguration-metamorphmagus` | 2 |
| `transfiguration-self-transformation-risk` | `transfiguration-self` | `transfiguration-human-transfiguration` | 2 |
| `transfiguration-vanishing-complexity` | `transfiguration-vanishing` | `transfiguration-vanishing-spell` | 2 |
| `transfiguration-vanishing-spell` | `transfiguration-vanishing` | `transfiguration-vanishing-spell` | 2 |

## Reproduce

```text
uv run python scripts/build_seeds.py --subject transfiguration --index-hash auto
uv run python scripts/author_subject.py transfiguration
uv run python scripts/author_subject.py transfiguration --mark-reviewed
uv run python scripts/author_subject.py transfiguration --publish
uv run pytest tests
```

A rebuild on an existing published pack needs `--force` on the draft
rebuild. `--mark-reviewed` is the explicit maintainer-approval step;
`--publish` refuses if any material is still draft.

## Scope notes

- The definition and limits of Transfiguration are covered.
- Object, creature and self-transfiguration are covered.
- Vanishing, Conjuring and switching are covered with their limits.
- Reversal and partial transfiguration are covered.
- Charms and DADA spellcraft are left to their own packs.
