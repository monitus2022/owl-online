"""Spike parsers for Lexicon entry and chapter pages.

HTML from hp-lexicon.org is regular WordPress markup. The observed anchors
(docs/lexicon-canon-index.md, Spike findings):

- citation codes live anywhere in the article: a curated "References from the
  canon" / "Canon references" section (a `<ul>` of `<li>` or a run of `<p>`
  blocks) and prose outside it; novel citations are
  `<a href="/source/the-harry-potter-novels/gf/gf6">GF6</a>`, non-novel ones
  are often bare parenthesials (`(WFT)`, `(BoS4)`, `(CG48)`, `(Pm)`);
- the article region runs from the `<h1>` to the first `related_container`;
  everything after is the sidebar fact box and the site-footer chapter
  navigation, which links every chapter of every book on every page, so the
  boundary is mandatory and a page without it fails loudly;
- `<div class="data">Label <span>value</span></div>` info lines (Incantation,
  Magic Type links, Abbreviation, Canonicity);
- Related Entries tabs of `<a class="relatedlink related-<group>" href="...">`
  form the reverse chapter-to-entry index; group names drift between plural
  (`characters`) and singular (`magic`) and are normalised;
- chapter url path carries the identity: /source/the-harry-potter-novels/gf/gf6/.

Only structure is extracted: titles, hrefs, codes. Bullet prose is read just
far enough to locate citation codes inside it and is never returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipeline.ingest.lexicon.codes import BUCKET_UNKNOWN, classify

NOVEL_URL_RE = re.compile(
    r"/source/the-harry-potter-novels/(?P<code>ps|cs|pa|gf|op|hbp|dh)/"
    r"(?P<slug>(?P=code)(?P<chapter>\d+)|dhe)/?",
    re.IGNORECASE,
)
A_RE = re.compile(r'<a\s[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<text>.*?)</a>', re.S)
RELATEDLINK_RE = re.compile(
    r'<a\s+class="relatedlink related-(?P<group>\w+)"\s+href="(?P<href>[^"]+)"'
    r"[^>]*>(?P<text>.*?)</a>",
    re.S,
)
DATA_RE = re.compile(r'<div class="data">(?P<body>.*?)</div>', re.S)
PAREN_RE = re.compile(r"\(([^)]{1,40})\)")
# One bullet can cite several sources: `(DH10, DH26)`, `(PS1 and PS2)`.
_MULTI_SPLIT_RE = re.compile(r",|&|\band\b")
_TAG_RE = re.compile(r"<[^>]+>")
REFERENCE_HEADINGS = ("References from the canon", "Canon references")

# Site tab names drift singular/plural; normalise to one canonical family.
_GROUP_ALIASES = {
    "characters": "character",
    "things": "thing",
    "creatures": "creature",
    "locations": "location",
    "places": "place",
    "essays": "essay",
    "quotes": "quote",
    "trivias": "trivia",
    "magic": "magic",
}


def normalise_group(raw: str) -> str:
    return _GROUP_ALIASES.get(raw.lower(), raw.lower())


def _looks_like_code(token: str) -> bool:
    """Shape gate for the review queue: unknown parenthesials that could be
    source abbreviations (digit-bearing like `SDNY2015`? or shouty like
    `MACUSA`), not prose like `(see below)` or `(Molly)`. Known table codes
    bypass this and are always recorded."""
    if not re.fullmatch(r"[A-Za-z0-9./]{2,12}(?::Tw)?", token):
        return False
    letters = [c for c in token if c.isalpha()]
    if any(c.isdigit() for c in token):
        return bool(letters)
    return bool(letters) and token == token.upper()


@dataclass(frozen=True)
class Citation:
    """One citation code found on an entry page, before normalisation."""

    code: str
    href: str | None
    origin: str  # href | anchor | bare | references-bare


@dataclass
class EntryPage:
    """Structure harvested from one concept entry page."""

    url: str
    title: str = ""
    incantation: str = ""
    magic_types: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    related_groups: dict[str, int] = field(default_factory=dict)
    has_references_section: bool = False
    unknown_tokens: list[str] = field(default_factory=list)


@dataclass
class ChapterPage:
    """Structure harvested from one novel-chapter source page."""

    url: str
    code: str = ""
    chapter_num: int | None = None
    is_epilogue: bool = False
    abbreviation: str = ""
    canonicity: str = ""
    related: list[tuple[str, str, str]] = field(default_factory=list)


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html)


def _article_region(html: str) -> str:
    """Body text from the title to the Related Entries container.

    Everything after `related_container` is sidebar and footer chrome; the
    footer lists every novel chapter link on every page. A page with no
    boundary after the title fails loudly instead of silently scanning the
    footer.
    """
    start = html.find("<h1")
    if start == -1:
        raise ValueError("no <h1 title found")
    end = html.find("related_container", start)
    if end == -1:
        raise ValueError("no related_container boundary before the footer")
    return html[start:end]


def _has_references_heading(region: str) -> bool:
    return any(heading in region for heading in REFERENCE_HEADINGS)


def _derive_code_from_href(href: str) -> str | None:
    """Novel chapter urls carry the code: .../gf/gf6 -> GF6, .../dh/dhe -> DHE."""
    m = NOVEL_URL_RE.search(href)
    if not m:
        return None
    if m.group("slug").lower() == "dhe":
        return "DHE"
    return f"{m.group('code').upper()}{m.group('chapter')}"


def parse_entry_page(html: str, url: str) -> EntryPage:
    """Harvest identity, citations and info lines from one entry page."""
    page = EntryPage(url=url)
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        page.title = _strip_tags(m.group(1)).strip()

    for div in DATA_RE.finditer(html):
        body = div.group("body")
        label = _strip_tags(body.split("<span", 1)[0]).strip()
        if label == "Incantation":
            page.incantation = _strip_tags(body.split(">", 1)[-1]).strip()
        elif label == "Magic Type":
            page.magic_types = [
                _strip_tags(a.group("text")).strip() for a in A_RE.finditer(body)
            ]

    region = _article_region(html)
    page.has_references_section = _has_references_heading(region)

    seen: set[str] = set()

    def record(token: str, href: str | None, origin: str) -> None:
        citation = classify(token)
        if citation.bucket == BUCKET_UNKNOWN:
            if _looks_like_code(citation.code) and citation.code not in page.unknown_tokens:
                page.unknown_tokens.append(citation.code)
            return
        if citation.code in seen:
            return
        seen.add(citation.code)
        page.citations.append(Citation(code=token, href=href, origin=origin))

    # Novel codes are trustworthy from the href alone, anywhere in the region.
    for anchor in A_RE.finditer(region):
        href = anchor.group("href")
        if "/source/" not in href:
            continue
        derived = _derive_code_from_href(href)
        if derived is not None:
            record(derived, href, "href")
        else:
            text = _strip_tags(anchor.group("text")).strip()
            record(text, href, "anchor")

    # Bare parenthesials anywhere in the region: the site's convention for
    # non-novel sources, including multi-code lists.
    for group in PAREN_RE.findall(_strip_tags(region)):
        for token in (t.strip() for t in _MULTI_SPLIT_RE.split(group)):
            record(token, None, "bare")

    groups: dict[str, int] = {}
    for rel in RELATEDLINK_RE.finditer(html):
        group = normalise_group(rel.group("group"))
        groups[group] = groups.get(group, 0) + 1
    page.related_groups = groups
    return page


def parse_chapter_page(html: str, url: str) -> ChapterPage:
    """Harvest the chapter identity, the info block and the reverse index."""
    page = ChapterPage(url=url)
    m = NOVEL_URL_RE.search(url)
    if not m:
        raise ValueError(f"not a novel chapter url: {url}")
    page.code = m.group("code").upper()
    page.is_epilogue = m.group("slug").lower() == "dhe"
    page.chapter_num = None if page.is_epilogue else int(m.group("chapter"))

    for div in DATA_RE.finditer(html):
        body = div.group("body")
        label = _strip_tags(body.split("<span", 1)[0]).strip()
        if label == "Abbreviation":
            page.abbreviation = _strip_tags(body.split(">", 1)[-1]).strip()
        elif label == "Canonicity":
            page.canonicity = _strip_tags(body.split(">", 1)[-1]).strip()

    for rel in RELATEDLINK_RE.finditer(html):
        page.related.append(
            (
                normalise_group(rel.group("group")),
                _strip_tags(rel.group("text")).strip(),
                rel.group("href"),
            )
        )
    return page
