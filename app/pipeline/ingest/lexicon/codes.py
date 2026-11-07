"""Citation-code grammar for the Lexicon canon index (spike).

The Lexicon abbreviates its sources: `GF6` is Goblet of Fire chapter 6,
`BoS4` is The Book of Spells chapter 4, `CG48` is The Crimes of Grindelwald
screenplay, and a trailing `/f` or `/g` marks the film or game version of a
novel code. Buckets follow the canon tiers in `docs/workplan.md` and
`docs/lexicon-canon-index.md`:

- `books`: the seven novels, the only future source refs;
- `secondary-books`: the Rowling companion books, recorded references only;
- `excluded`: screenplays, films, games and other canon, recorded and tagged;
- `unknown`: a code the grammar does not know; the caller queues it for review.

A `/f` or `/g` suffix sends any code to `excluded`, including `DHE`: the film
medium can never enter the books bucket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NOVEL_BY_CODE = {
    "PS": 1,
    "CS": 2,
    "PA": 3,
    "GF": 4,
    "OP": 5,
    "HBP": 6,
    "DH": 7,
}

# Companion books and other sources, by their Lexicon abbreviation.
SECONDARY_BOOK_CODES = {"QA", "FB", "TBB", "BoS", "BoP"}
EXCLUDED_CODES = {
    "WFT", "CG", "SD", "CC",  # screenplays and the play
    "PM", "Pm", "JKR", "DP", "FW", "BFT", "Pre", "HPM", "MagSp",
}

# Chapter counts of the seven novels in our corpus (data/chunks.jsonl).
NOVEL_CHAPTER_COUNTS = {1: 17, 2: 18, 3: 22, 4: 37, 5: 38, 6: 30, 7: 36}

# The Lexicon cites the Deathly Hallows epilogue as `DHE`, without a number.
# It is book 7 chapter 36 in our corpus, whose last chunks hold the epilogue;
# `is_epilogue` keeps the identity distinct from a plain chapter-36 citation.
EPILOGUE_CODE = "DHE"

BUCKET_BOOKS = "books"
BUCKET_SECONDARY = "secondary-books"
BUCKET_EXCLUDED = "excluded"
BUCKET_UNKNOWN = "unknown"

# Order longest-first, then by name, so `HBP` wins over `HP`-style prefixes
# and the alternation is byte-stable across processes (deterministic rule).
_CODES = sorted(
    {
        *NOVEL_BY_CODE,
        *SECONDARY_BOOK_CODES,
        *EXCLUDED_CODES,
        EPILOGUE_CODE,
    },
    key=lambda code: (-len(code), code),
)
CITATION_RE = re.compile(
    r"\b(" + "|".join(_CODES) + r")(?::Tw)?(?:\s*(\d+(?:\.\d+)?))?(?:/([fg]))?\b"
)

# Beedle the Bard is cited per tale: `TBB/BR`, `TBB/WHH` (the canon page lists
# named tale pages). Tale-level codes are secondary books.
TALE_CODE_RE = re.compile(r"TBB/([A-Z]{2,4})")

# Source pages carry the same information as the abbreviation table in the
# url path, so an unlinked or mislabeled anchor can still be bucketed.
SECONDARY_SOURCE_SLUGS = {"qa", "fb", "tbb"}
SOURCE_PATH_RE = re.compile(r"/source/(?:[a-z-]+/)*(?P<slug>[a-z0-9-]+)/?$")


@dataclass(frozen=True)
class ResolvedCitation:
    """One citation code, normalised against the source table."""

    code: str
    bucket: str
    book_num: int | None = None
    chapter_num: int | None = None
    medium: str = "book"  # book | film | game | screenplay | other
    is_epilogue: bool = False

    @property
    def usable_for_packs(self) -> bool:
        return self.bucket == BUCKET_BOOKS


def classify(raw: str) -> ResolvedCitation:
    """Resolve one citation code, exactly as it appears on the page.

    Raises ValueError for an empty code. An unrecognised abbreviation returns
    bucket `unknown` so the caller collects it into a review queue; the caller
    never drops it.
    """
    code = raw.strip()
    if not code:
        raise ValueError("empty citation code")
    tale = TALE_CODE_RE.fullmatch(code)
    if tale:
        return ResolvedCitation(
            code=code, bucket=BUCKET_SECONDARY, medium="other"
        )
    m = CITATION_RE.fullmatch(code)
    if m is None:
        return ResolvedCitation(code=code, bucket=BUCKET_UNKNOWN)
    prefix, chapter_text, medium_suffix = m.groups()
    if chapter_text is None:
        chapter_num: int | None = None
    else:
        # Scene-style numbers (`CC3.9`) keep the code but no chapter int.
        try:
            chapter_num = int(chapter_text)
        except ValueError:
            chapter_num = None
    # The medium suffix outranks everything: a film or game citation is never
    # books, including the epilogue code.
    if medium_suffix:
        return ResolvedCitation(
            code=code,
            bucket=BUCKET_EXCLUDED,
            book_num=NOVEL_BY_CODE.get(prefix),
            chapter_num=chapter_num,
            medium="film" if medium_suffix == "f" else "game",
        )
    if prefix == EPILOGUE_CODE:
        return ResolvedCitation(
            code=code,
            bucket=BUCKET_BOOKS,
            book_num=7,
            chapter_num=36,
            is_epilogue=True,
        )
    if prefix in NOVEL_BY_CODE:
        return ResolvedCitation(
            code=code,
            bucket=BUCKET_BOOKS,
            book_num=NOVEL_BY_CODE[prefix],
            chapter_num=chapter_num,
        )
    if prefix in SECONDARY_BOOK_CODES:
        return ResolvedCitation(
            code=code,
            bucket=BUCKET_SECONDARY,
            chapter_num=chapter_num,
            medium="other",
        )
    return ResolvedCitation(code=code, bucket=BUCKET_EXCLUDED, medium="other")


def chapter_is_valid(resolved: ResolvedCitation) -> bool:
    """True when a books-bucket citation points at a chapter our corpus has."""
    if resolved.book_num is None or resolved.chapter_num is None:
        return True
    return 1 <= resolved.chapter_num <= NOVEL_CHAPTER_COUNTS[resolved.book_num]


def known_code(raw: str) -> str | None:
    """The table spelling for a case-folded slug (`bos` -> `BoS`), if known.

    Prefers the all-caps variant when two table codes fold to the same key.
    """
    matches = [c for c in _CODES if c.casefold() == raw.casefold()]
    if not matches:
        return None
    return next((c for c in sorted(matches) if c.isupper()), sorted(matches)[0])


def classify_source_href(href: str) -> ResolvedCitation | None:
    """Bucket a /source/ page url by its path, without the anchor text.

    Novel chapter urls belong to `parse._derive_code_from_href` (they carry a
    chapter number); this covers the rest: companion books are secondary,
    anything else the site treats as a source page is excluded canon. Returns
    None when the href is not a source page.
    """
    m = SOURCE_PATH_RE.search(href)
    if not m:
        return None
    slug = m.group("slug")
    if (
        slug.startswith("tbb")
        and 3 < len(slug) <= 7
        and slug[3:].isalpha()
    ):
        return ResolvedCitation(
            code=f"TBB/{slug[3:].upper()}", bucket=BUCKET_SECONDARY, medium="other"
        )
    if slug in SECONDARY_SOURCE_SLUGS:
        return ResolvedCitation(
            code=slug.upper(), bucket=BUCKET_SECONDARY, medium="other"
        )
    letters = re.match(r"[a-zA-Z]+", slug)
    if not letters:
        return None
    raw = letters.group(0)
    # Prefer a code the table knows in any casing; an unlisted path slug is
    # an excluded source under its upper-cased abbreviation.
    code = known_code(raw)
    resolved = classify(code) if code else None
    if resolved is None or resolved.bucket == BUCKET_UNKNOWN:
        return ResolvedCitation(code=raw.upper(), bucket=BUCKET_EXCLUDED, medium="other")
    if resolved.bucket == BUCKET_BOOKS:
        # A bare novel root (/source/the-harry-potter-novels/ps/) is a
        # book-level edge; chapter stays None.
        return ResolvedCitation(
            code=resolved.code, bucket=BUCKET_BOOKS, book_num=resolved.book_num
        )
    return resolved
