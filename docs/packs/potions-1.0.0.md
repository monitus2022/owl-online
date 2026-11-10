# Potions subject pack 1.0.0

- Date: 2026-11-10
- Subject: `potions`
- Version: `1.0.0`
- Status: `published`
- Fingerprint: `578f4b2cb74569a7`
- Index text hash: `aca4c57462d449f5`
- Materials: 34
- Concepts: 34
- Topics: 6
- Source refs: 119
- Reviewed materials: 34/34

## Validation

```text
validate_pack: ok=True errors=0 warnings=0
materials=34 concepts=34 topics=6
fingerprint=578f4b2cb74569a7
```

The pack directory is gitignored. This record is structure-only and
contains no corpus text; the material prose stays in the local pack and
the data backup.

## Topic coverage

| Topic | Materials |
|---|---:|
| `potions-danger` | 5 |
| `potions-foundations` | 6 |
| `potions-healing` | 7 |
| `potions-legendary` | 4 |
| `potions-mind` | 7 |
| `potions-transformation` | 5 |

## Kind mix

| Kind | Materials |
|---|---:|
| `definition` | 5 |
| `event` | 1 |
| `object` | 3 |
| `potion` | 21 |
| `procedure` | 4 |

## Materials

| Material id | Topic | Concept | Refs |
|---|---|---|---:|
| `potions-danger-accidents` | `potions-danger` | `potions-event-potion-accident` | 4 |
| `potions-danger-antidote-limits` | `potions-danger` | `potions-definition-antidote-limits` | 4 |
| `potions-danger-contamination` | `potions-danger` | `potions-definition-contamination` | 2 |
| `potions-danger-ingredients` | `potions-danger` | `potions-object-dangerous-ingredient` | 3 |
| `potions-danger-poison` | `potions-danger` | `potions-definition-poison` | 4 |
| `potions-foundation-brewing-method` | `potions-foundations` | `potions-procedure-brewing` | 3 |
| `potions-foundation-cauldron` | `potions-foundations` | `potions-object-cauldron` | 4 |
| `potions-foundation-dosing` | `potions-foundations` | `potions-procedure-dosing` | 4 |
| `potions-foundation-ingredient-preparation` | `potions-foundations` | `potions-procedure-preparation` | 4 |
| `potions-foundation-potions-definition` | `potions-foundations` | `potions-definition-potions` | 3 |
| `potions-foundation-storage` | `potions-foundations` | `potions-procedure-storage` | 3 |
| `potions-healing-antidotes` | `potions-healing` | `potions-potion-antidote` | 4 |
| `potions-healing-bezoar` | `potions-healing` | `potions-object-bezoar` | 4 |
| `potions-healing-boil-cure` | `potions-healing` | `potions-potion-boil-cure` | 2 |
| `potions-healing-dittany` | `potions-healing` | `potions-potion-dittany` | 3 |
| `potions-healing-mandrake-draught` | `potions-healing` | `potions-potion-mandrake-draught` | 4 |
| `potions-healing-pepperup` | `potions-healing` | `potions-potion-pepperup` | 2 |
| `potions-healing-skele-gro` | `potions-healing` | `potions-potion-skele-gro` | 3 |
| `potions-legendary-elixir-of-life` | `potions-legendary` | `potions-potion-elixir-of-life` | 3 |
| `potions-legendary-felix-felicis` | `potions-legendary` | `potions-potion-felix-felicis` | 4 |
| `potions-legendary-living-death` | `potions-legendary` | `potions-potion-living-death` | 5 |
| `potions-legendary-wolfsbane` | `potions-legendary` | `potions-potion-wolfsbane` | 4 |
| `potions-mind-amortentia` | `potions-mind` | `potions-potion-amortentia` | 3 |
| `potions-mind-confusing-concoction` | `potions-mind` | `potions-potion-confusing-concoction` | 2 |
| `potions-mind-draught-of-peace` | `potions-mind` | `potions-potion-draught-of-peace` | 5 |
| `potions-mind-euphoria-elixir` | `potions-mind` | `potions-potion-euphoria-elixir` | 2 |
| `potions-mind-love-potion` | `potions-mind` | `potions-potion-love-potion` | 4 |
| `potions-mind-sleeping-draught` | `potions-mind` | `potions-potion-sleeping-draught` | 2 |
| `potions-mind-veritaserum` | `potions-mind` | `potions-potion-veritaserum` | 4 |
| `potions-transformation-deflating` | `potions-transformation` | `potions-potion-deflating` | 3 |
| `potions-transformation-polyjuice` | `potions-transformation` | `potions-potion-polyjuice` | 6 |
| `potions-transformation-polyjuice-limits` | `potions-transformation` | `potions-definition-polyjuice-limits` | 5 |
| `potions-transformation-shrinking` | `potions-transformation` | `potions-potion-shrinking` | 3 |
| `potions-transformation-swelling` | `potions-transformation` | `potions-potion-swelling` | 4 |

## Reproduce

```text
uv run python scripts/build_seeds.py --subject potions --index-hash auto
uv run python scripts/author_subject.py potions
uv run python scripts/author_subject.py potions --mark-reviewed
uv run python scripts/author_subject.py potions --publish
uv run pytest tests
```

A rebuild on an existing published pack needs `--force` on the draft
rebuild. `--mark-reviewed` is the explicit maintainer-approval step;
`--publish` refuses if any material is still draft.

## Scope notes

- Ingredients, brewing method, potency, storage and safety are covered.
- Healing draughts, antidotes and poison treatment are covered.
- Mind and transformation potions are covered, including their limits.
- Dangerous brews and legendary potions are covered.
- Charms and DADA spellcraft are left to their own packs.
