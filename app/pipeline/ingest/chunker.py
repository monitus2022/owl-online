import re
from dataclasses import dataclass

from app.schemas import Chunk, ChunkMetadata

# --- Numbers matching mapping ---

_UNITS = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
}
_TEENS = {
    "TEN": 10,
    "ELEVEN": 11,
    "TWELVE": 12,
    "THIRTEEN": 13,
    "FOURTEEN": 14,
    "FIFTEEN": 15,
    "SIXTEEN": 16,
    "SEVENTEEN": 17,
    "EIGHTEEN": 18,
    "NINETEEN": 19,
}
_TENS = {
    "TWENTY": 20,
    "THIRTY": 30,
    "FORTY": 40,
    "FIFTY": 50,
    "SIXTY": 60,
    "SEVENTY": 70,
    "EIGHTY": 80,
    "NINETY": 90,
}


def word2int(word: str) -> int:
    """Convert spelled-out chapter numbers ('TWENTY-EIGHT') into integers for RAG."""
    w = word.strip().upper()
    if w in _UNITS:
        return _UNITS[w]
    if w in _TEENS:
        return _TEENS[w]
    if w in _TENS:
        return _TENS[w]
    if "-" in w:
        tens, _, unit = w.partition("-")
        if tens in _TENS and unit in _UNITS:
            return _TENS[tens] + _UNITS[unit]
    raise ValueError(f"unparseable chapter number: {word!r}")


# --- Parse chapters ---

# Caps-only on purpose: a lowercase "chapter one" inside story text must not
# silently reset book/chapter counting.
CHAPTER_HEADING_RE = re.compile(r"(?m)^\s*CHAPTER\s+([A-Z\-]+)\s*$")
# Chapter title: the all-caps line following the heading (curly or straight apostrophes allowed)
CHAPTER_TITLE_RE = re.compile(r"^[A-Z0-9’' \-]+$")
# Characters of a page that are scanned for a chapter heading
_HEADING_SEARCH_WINDOW = 600

BOOK_NAMES = {
    1: "Harry Potter and the Sorcerer's Stone",
    2: "Harry Potter and the Chamber of Secrets",
    3: "Harry Potter and the Prisoner of Azkaban",
    4: "Harry Potter and the Goblet of Fire",
    5: "Harry Potter and the Order of the Phoenix",
    6: "Harry Potter and the Half-Blood Prince",
    7: "Harry Potter and the Deathly Hallows",
}


@dataclass(frozen=True)
class ParsedChapter:
    # Metadata
    book_num: int
    chapter_num: int
    book_name: str
    chapter_name: str
    page_start: int
    page_end: int  # Use next chapter's page start as reference
    text: str


def parse_chapters(pages: list[str]) -> list[ParsedChapter]:
    """Loop pages, chapter number starts a chapter, a CHAPTER ONE reset starts a book

    Text before the first heading (front matter) is dropped. Pages after a book's
    last chapter (title pages of the next book) attach to the previous chapter —
    ~1 page per book of noise, accepted for V1.
    """
    hits: list[tuple[int, int, str]] = []  # (page, chapter_num, chapter_name)
    for i, text in enumerate(pages):
        m = CHAPTER_HEADING_RE.search(text[:_HEADING_SEARCH_WINDOW])
        if not m:
            continue
        num = word2int(m.group(1))
        title = next(
            (
                ln
                for ln in text[m.end() :].splitlines()
                if ln.strip() and CHAPTER_TITLE_RE.match(ln.strip())
            ),
            "",
        ).strip()
        hits.append((i, num, title or f"Chapter {num}"))

    if not hits or hits[0][1] != 1:
        raise ValueError("no starting CHAPTER ONE found — corpus structure unexpected")

    chapters: list[ParsedChapter] = []
    book_num, chapter_count, prev_num = 1, 0, 0
    bounds = hits + [(len(pages), 0, "")]
    # strict=False is intentional: bounds has exactly one sentinel more than the
    # pairs we want — each hit zipped with its successor.
    for (start, num, name), (end, _, _) in zip(bounds, bounds[1:], strict=False):
        if num == 1 and chapter_count > 0:
            book_num += 1
            prev_num = 0
        chapter_count += 1
        if book_num > 7:
            raise ValueError(f"more than 7 books detected at page {start} — check heading regex")
        if num != prev_num + 1:
            # A stray/misspelled heading must fail loudly, not silently mislabel
            # every chunk after it.
            raise ValueError(
                f"chapter numbering not contiguous in book {book_num}: "
                f"{prev_num} -> {num} at page {start}"
            )
        prev_num = num
        chapters.append(
            ParsedChapter(
                book_num=book_num,
                chapter_num=num,
                book_name=BOOK_NAMES[book_num],
                chapter_name=name,
                page_start=start,
                page_end=end,
                text="\n".join(pages[start:end]),
            )
        )
    return chapters


# --- Chunking texts ---

# Default chunk params
_CHUNK_SIZE = 500
_OVERLAP = 75
_MIN_CHUNK_SIZE = 200


def chunk_text(
    text: str,
    *,
    chunk_size: int = _CHUNK_SIZE,
    overlap: int = _OVERLAP,
    min_size: int = _MIN_CHUNK_SIZE,
) -> list[str]:
    """Accumulate paragraphs up to chunk size target, with overlap
    If a paragraph is too long, split it at sentence boundaries
    If the last chunk is too small, merge it with the previous one

    Paragraphs = blank-line-separated blocks; oversized blocks are hard-split at
    sentence boundaries. Params move to the manifest in D7 (#53).
    """
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    pieces: list[str] = []
    for b in blocks:
        if len(b) > chunk_size * 1.5:
            sentences = re.split(r"(?<=[.!?])\s+", b)
            cur = ""
            for s in sentences:
                if cur and len(cur) + len(s) > chunk_size:
                    pieces.append(cur)
                    cur = s
                else:
                    cur = f"{cur} {s}".strip()
            if cur:
                pieces.append(cur)
        else:
            pieces.append(b)

    chunks: list[str] = []
    cur = ""
    for p in pieces:
        if cur and len(cur) + len(p) > chunk_size:
            chunks.append(cur)
            # overlap=0 degrades cur[-0:] to the whole string — guard the explicit zero
            tail = cur[-overlap:] if overlap > 0 else ""
            cut = tail.find(" ")
            cur = (tail[cut + 1 :] if cut != -1 else tail) + " " + p
        else:
            cur = f"{cur} {p}".strip()
    if cur:
        chunks.append(cur)

    if len(chunks) > 1 and len(chunks[-1]) < min_size:
        # pop() first, then index: `chunks[-2] += ... chunks.pop()` evaluates the
        # RHS first, and with exactly 2 chunks the pop leaves chunks[-2] out of range.
        last = chunks.pop()
        chunks[-1] += " " + last
    return chunks


def make_chunks(
    chapter: ParsedChapter,
    *,
    chunk_size: int = _CHUNK_SIZE,
    overlap: int = _OVERLAP,
    min_size: int = _MIN_CHUNK_SIZE,
) -> list[Chunk]:
    """Chunk one chapter into validated Chunk objects with sequential ids."""
    pieces = chunk_text(chapter.text, chunk_size=chunk_size, overlap=overlap, min_size=min_size)
    metadata = ChunkMetadata(
        book_num=chapter.book_num,
        chapter_num=chapter.chapter_num,
        book_name=chapter.book_name,
        chapter_name=chapter.chapter_name,
    )
    return [
        Chunk(
            id=f"b{chapter.book_num}-c{chapter.chapter_num:02d}-{i:04d}",
            text=piece,
            metadata=metadata,
        )
        for i, piece in enumerate(pieces)
    ]
