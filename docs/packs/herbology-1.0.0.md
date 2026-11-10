# Herbology subject pack 1.0.0

- Date: 2026-11-10
- Subject: `herbology`
- Version: `1.0.0`
- Status: `published`
- Fingerprint: `da6804d846814ec9`
- Index text hash: `aca4c57462d449f5`
- Materials: 33
- Concepts: 31
- Topics: 6
- Source refs: 89
- Reviewed materials: 33/33

## Validation

```text
validate_pack: ok=True errors=0 warnings=0
materials=33 concepts=31 topics=6
fingerprint=da6804d846814ec9
```

The pack directory is gitignored. This record is structure-only and
contains no corpus text; the material prose stays in the local pack and
the data backup.

## Topic coverage

| Topic | Materials |
|---|---:|
| `herbology-aquatic` | 3 |
| `herbology-dangerous` | 10 |
| `herbology-foundations` | 6 |
| `herbology-fungi` | 5 |
| `herbology-harvest` | 5 |
| `herbology-medicinal` | 4 |

## Kind mix

| Kind | Materials |
|---|---:|
| `definition` | 1 |
| `object` | 25 |
| `place` | 2 |
| `procedure` | 5 |

## Materials

| Material id | Topic | Concept | Refs |
|---|---|---|---:|
| `herbology-aquatic-gillyweed` | `herbology-aquatic` | `herbology-thing-gillyweed` | 3 |
| `herbology-aquatic-gillyweed-effects` | `herbology-aquatic` | `herbology-thing-gillyweed` | 4 |
| `herbology-aquatic-water-plants-guide` | `herbology-aquatic` | `herbology-thing-magical-water-plants-mediterranean` | 2 |
| `herbology-dangerous-bubotuber` | `herbology-dangerous` | `herbology-thing-bubotuber` | 3 |
| `herbology-dangerous-bubotuber-pus` | `herbology-dangerous` | `herbology-thing-bubotuber-pus` | 2 |
| `herbology-dangerous-devils-snare` | `herbology-dangerous` | `herbology-thing-devils-snare` | 3 |
| `herbology-dangerous-devils-snare-disguise` | `herbology-dangerous` | `herbology-thing-devils-snare` | 2 |
| `herbology-dangerous-snargaluff` | `herbology-dangerous` | `herbology-thing-snargaluff` | 3 |
| `herbology-dangerous-snargaluff-pods` | `herbology-dangerous` | `herbology-thing-snargaluff-pods` | 5 |
| `herbology-dangerous-tentacula-seeds` | `herbology-dangerous` | `herbology-thing-venomous-tentacula-seeds` | 2 |
| `herbology-dangerous-venomous-tentacula` | `herbology-dangerous` | `herbology-thing-venomous-tentacula` | 2 |
| `herbology-dangerous-whomping-willow` | `herbology-dangerous` | `herbology-thing-whomping-willow` | 3 |
| `herbology-dangerous-whomping-willow-knot` | `herbology-dangerous` | `herbology-procedure-whomping-willow-knot` | 3 |
| `herbology-foundations-dragon-dung-compost` | `herbology-foundations` | `herbology-thing-dragon-dung-compost` | 3 |
| `herbology-foundations-greenhouse-three` | `herbology-foundations` | `herbology-place-greenhouse-three` | 2 |
| `herbology-foundations-greenhouses` | `herbology-foundations` | `herbology-place-greenhouses` | 4 |
| `herbology-foundations-protective-equipment` | `herbology-foundations` | `herbology-procedure-protective-equipment` | 5 |
| `herbology-foundations-repotting` | `herbology-foundations` | `herbology-procedure-repotting` | 2 |
| `herbology-foundations-subject` | `herbology-foundations` | `herbology-definition-herbology` | 1 |
| `herbology-fungi-dirigible-plum` | `herbology-fungi` | `herbology-thing-dirigible-plum` | 2 |
| `herbology-fungi-gurdyroot` | `herbology-fungi` | `herbology-thing-gurdyroot` | 3 |
| `herbology-fungi-mimbulus-mimbletonia` | `herbology-fungi` | `herbology-thing-mimbulus-mimbletonia` | 3 |
| `herbology-fungi-puffapod` | `herbology-fungi` | `herbology-thing-puffapod` | 1 |
| `herbology-fungi-stinksap` | `herbology-fungi` | `herbology-thing-stinksap` | 3 |
| `herbology-harvest-abyssinian-shrivelfig` | `herbology-harvest` | `herbology-thing-abyssinian-shrivelfig` | 2 |
| `herbology-harvest-flutterby-bush` | `herbology-harvest` | `herbology-thing-flutterby-bush` | 2 |
| `herbology-harvest-mandrake-maturation` | `herbology-harvest` | `herbology-procedure-mandrake-maturation` | 4 |
| `herbology-harvest-pruning` | `herbology-harvest` | `herbology-procedure-pruning` | 3 |
| `herbology-harvest-screechsnap` | `herbology-harvest` | `herbology-thing-screechsnap` | 1 |
| `herbology-medicinal-aconite` | `herbology-medicinal` | `herbology-thing-aconite` | 2 |
| `herbology-medicinal-dittany` | `herbology-medicinal` | `herbology-thing-dittany` | 2 |
| `herbology-medicinal-mandrake` | `herbology-medicinal` | `herbology-thing-mandrake` | 4 |
| `herbology-medicinal-nettles` | `herbology-medicinal` | `herbology-thing-nettles` | 3 |

## Reproduce

```text
uv run python scripts/build_seeds.py --subject herbology --index-hash auto
uv run python scripts/author_subject.py herbology
uv run python scripts/author_subject.py herbology --mark-reviewed
uv run python scripts/author_subject.py herbology --publish
uv run pytest tests
```

A rebuild on an existing published pack needs `--force` on the draft
rebuild. `--mark-reviewed` is the explicit maintainer-approval step;
`--publish` refuses if any material is still draft.

## Scope notes

- Magical plants, greenhouses, care and safety are covered.
- Medicinal and dangerous plants are covered.
- Aquatic plants and fungi are covered.
- Harvesting, propagation and preservation are covered.
- Charms and DADA spellcraft are left to their own packs.
