# DADA subject pack 1.0.0

- Date: 2026-11-08
- Subject: `dada`
- Version: `1.0.0`
- Status: `published`
- Fingerprint: `e7139cbcc23eaa5c`
- Index text hash: `aca4c57462d449f5`
- Materials: 25
- Concepts: 21
- Topics: 4
- Review: maintainer prose review, 2026-11-08

## Validation

```text
validate_pack: ok=True errors=0 warnings=0
materials=25 concepts=21 topics=4
fingerprint=e7139cbcc23eaa5c
```

The pack directory is gitignored. This record is structure-only and
contains no corpus text; the material prose stays in the local pack and
the data backup.

## Materials

| Material id | Topic | Concept | Refs |
|---|---|---|---|
| `dada-countering-countercurse-doctrine` | `defensive-magic` | `dada-magic-countercurse` | 5 |
| `dada-countering-detection-and-concealment` | `defensive-magic` | `dada-magic-concealment-charm` | 4 |
| `dada-countering-hex-deflection` | `defensive-magic` | `dada-magic-hex-deflection` | 4 |
| `dada-dark-arts-cruciatus-evidence` | `dark-arts` | `dada-magic-cruciatus-curse` | 3 |
| `dada-dark-arts-imperius-demonstration` | `dark-arts` | `dada-magic-imperius-curse` | 6 |
| `dada-dark-arts-killing-curse-limits` | `dark-arts` | `dada-magic-killing-curse` | 4 |
| `dada-dark-arts-unforgivables-law` | `dark-arts` | `dada-magic-unforgivable-curses` | 3 |
| `dada-dark-creatures-boggarts-counter` | `dark-creatures` | `dada-magic-boggart-banishing-spell` | 7 |
| `dada-dark-creatures-boggarts-field` | `dark-creatures` | `dada-creature-boggart` | 5 |
| `dada-dark-creatures-boggarts-nature` | `dark-creatures` | `dada-creature-boggart` | 3 |
| `dada-dark-creatures-dementors-nature` | `dark-creatures` | `dada-creature-dementors` | 5 |
| `dada-dark-creatures-fieldcraft-pixies` | `dark-creatures` | `dada-creature-pixie` | 6 |
| `dada-dark-creatures-fieldcraft-thestrals` | `dark-creatures` | `dada-creature-thestral` | 7 |
| `dada-dark-creatures-fieldcraft-water-and-marsh` | `dark-creatures` | `dada-creature-grindylow` | 6 |
| `dada-dark-creatures-grim-private-fear` | `dark-creatures` | `dada-creature-grim` | 2 |
| `dada-dark-creatures-werewolves-law-and-fear` | `dark-creatures` | `dada-creature-werewolf` | 4 |
| `dada-dark-creatures-werewolves-recognition` | `dark-creatures` | `dada-creature-werewolf` | 6 |
| `dada-dueling-disarming-charm` | `dueling` | `dada-magic-disarming-charm` | 9 |
| `dada-dueling-shield-charm` | `defensive-magic` | `dada-magic-shield-charm` | 4 |
| `dada-dueling-stunning-spell` | `dueling` | `dada-magic-stunning-spell` | 8 |
| `dada-magic-patronus-theory` | `defensive-magic` | `dada-magic-patronus` | 5 |
| `dada-magic-patronus-training` | `defensive-magic` | `dada-magic-corporeal-patronus` | 7 |
| `dada-protective-fidelius-trust` | `defensive-magic` | `dada-magic-fidelius-charm` | 4 |
| `dada-protective-patronus-field` | `defensive-magic` | `dada-magic-patronus` | 4 |
| `dada-protective-wards-at-scale` | `defensive-magic` | `dada-magic-shield-charm` | 4 |

## Lesson table

The DADA table has 53 approved rows. The materials audit struck three
non-DADA rows (`b1 c8`, `b2 c12`, `b2 c13`), added five rows (`b3 c18`,
`b5 c22`, `b5 c31`, `b6 c02`, `b7 c06`), and re-based non-classroom rows
to `author-pick` with their actual teaching context.

## Reproduce

```text
uv run python scripts/build_seeds.py --subject dada --index-hash auto
uv run python scripts/author_dada_units.py   # refuses a published pack without --force
uv run python scripts/run_eval.py --check
```

A rebuild with `--force` writes a reviewed draft, not the published 1.0.0
artifact. Publication is the separate maintainer step recorded in
`data/subjects/dada/PUBLISH.md` (local, gitignored, in the data backup).
