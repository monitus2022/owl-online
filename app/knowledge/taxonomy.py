"""Subject taxonomy: the twelve O.W.L. subjects, tiers and controlled vocabularies.

The subject set and the vocabularies (tiers, concept kinds, canon tier/scope,
review status) are fixed here in code; they are not editable data. Topics,
concepts and materials are per-subject data under `data/subjects/<subject>/`
and are defined in `materials.py` and `packs.py`.

Canonical source policy (`docs/workplan.md`, `docs/lexicon-canon-index.md`):
the seven novels are the only primary, exam-gradable canon. A material marked
`canon_tier=primary` must carry `canon_scope=books`; film, game and secondary
citations are recorded but never become source refs.
"""

from __future__ import annotations

from dataclasses import dataclass

# Controlled vocabularies. Kept as ordered tuples so loaders and reports are
# deterministic; validated as sets at the model boundary.
SUBJECTS: tuple[tuple[str, str], ...] = (
    ("astronomy", "Astronomy"),
    ("charms", "Charms"),
    ("dada", "Defence Against the Dark Arts"),
    ("herbology", "Herbology"),
    ("history-of-magic", "History of Magic"),
    ("potions", "Potions"),
    ("transfiguration", "Transfiguration"),
    ("ancient-runes", "Ancient Runes"),
    ("arithmancy", "Arithmancy"),
    ("divination", "Divination"),
    ("care-of-magical-creatures", "Care of Magical Creatures"),
    ("muggle-studies", "Muggle Studies"),
)

TIERS: tuple[str, ...] = ("owl", "newt")

# How a concept is realised in the books. A spell, potion, creature, etc.
CONCEPT_KINDS: tuple[str, ...] = (
    "spell",
    "potion",
    "creature",
    "object",
    "place",
    "event",
    "character",
    "definition",
    "procedure",
)

# Canon tiers from docs/workplan.md. Only `primary` is exam-gradable.
CANON_TIERS: tuple[str, ...] = ("primary", "secondary", "tertiary", "excluded")
# Canon scope: which medium the fact comes from. Excludes films and games from
# the books pack even when the site cites them.
CANON_SCOPES: tuple[str, ...] = ("books", "films", "games")
# Review status. Only `reviewed` material may publish; the validator enforces.
REVIEW_STATUSES: tuple[str, ...] = ("draft", "reviewed", "rejected")

# The seven novels, 1-indexed, matching ChunkMetadata.book_num.
NOVEL_BOOKS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7)
BOOK_NAMES: dict[int, str] = {
    1: "Philosopher's Stone",
    2: "Chamber of Secrets",
    3: "Prisoner of Azkaban",
    4: "Goblet of Fire",
    5: "Order of the Phoenix",
    6: "Half-Blood Prince",
    7: "Deathly Hallows",
}

SUBJECT_KEYS = frozenset(key for key, _ in SUBJECTS)
SUBJECT_NAMES = dict(SUBJECTS)
TIER_SET = frozenset(TIERS)
KIND_SET = frozenset(CONCEPT_KINDS)
CANON_TIER_SET = frozenset(CANON_TIERS)
CANON_SCOPE_SET = frozenset(CANON_SCOPES)
REVIEW_SET = frozenset(REVIEW_STATUSES)


@dataclass(frozen=True)
class Subject:
    """One of the twelve O.W.L. subjects."""

    key: str
    name: str
    tiers: tuple[str, ...] = ("owl",)


def known_subject(key: str) -> Subject | None:
    for k, name in SUBJECTS:
        if k == key:
            return Subject(key=k, name=name)
    return None
