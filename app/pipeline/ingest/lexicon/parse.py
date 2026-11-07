"""Spike parsers for Lexicon entry and chapter pages.

HTML from hp-lexicon.org is regular WordPress markup. The observed anchors
(docs/lexicon-canon-index.md, Site anatomy; refined by the #125 sample crawl):

- citation codes live anywhere in the article region: a curated "References
  from the canon" / "Canon references" section (a `<ul>` of `<li>` or a run of
  `<p>` blocks), and prose elsewhere; novel citations are
  `<a href="/source/the-harry-potter-novels/gf/gf6">GF6</a>`, non-novel ones
  are often bare parenthesials (`(WFT)`, `(BoS4)`, `(CG48)`, `(Pm)`);
- the article region ends at the first `related_container`: the sidebar fact
  box and the site-footer chapter navigation (which links every chapter of
  every book on every page) sit outside it and must not be scanned;
- `<div class="data">Label <span>value</span></div>` info lines (Incantation,
  Magic Type links, Abbreviation, Canonicity);
- Related Entries tabs of `<a class="relatedlink related-<group>" href="...">`
  form the reverse chapter-to-entry index;
- chapter url path carries the identity: /source/the-harry-potter-novels/gf/gf6/.

Only structure is extracted: titles, hrefs, codes. Bullet prose is read just
far enough to locate citation codes inside it and is never returned.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pipeline.ingest.lexicon.codes import classify

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
# A parenthesised token that looks like a source code but is not in the table;
# it goes to the review queue instead of being dropped. Parenthetical prose
# ("see below", "ditto") is filtered by the upper/digit requirement.
CODEISH_RE = re.compile(r"[A-Za-z0-9./]{2,12}(?::Tw)?")
_TAG_RE = re.compile(r"<[^>]+>")
REFERENCE_HEADINGS = ("References from the canon", "Canon references")


def _is_codeish(token: str) -> bool:
    """A parenthesised token worth classifying: code-shaped, not prose."""
    return bool(CODEISH_RE.fullmatch(token)) and any(
        c.isupper() or c.isdigit() for c in token
    )


@dataclass(frozen=True)
class Citation:
    """One citation code found on an entry page, before normalisation."""

    code: str
    href: str | None
    origin: str  # href | anchor | bare


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
    footer lists every novel chapter link on every page.
    """
    start = html.find("<h1")
    end = html.find("related_container")
    if end == -1:
        end = len(html)
    return html[start:end] if start != -1 else html[:end]


def _references_sections(html: str) -> str:
    """Concatenate the blocks that follow a references heading, if any."""
    chunks: list[str] = []
    for heading in REFERENCE_HEADINGS:
        pos = 0
        while True:
            pos = html.find(heading, pos)
            if pos == -1:
                break
            end = html.find("<h2", pos)
            chunks.append(html[pos:end if end != -1 else len(html)])
            pos += len(heading)
    return "\n".join(chunks)


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

    refs_html = _references_sections(html)
    page.has_references_section = bool(refs_html)
    article = _article_region(html)

    seen: set[str] = set()

    def record(token: str, href: str | None, origin: str) -> None:
        citation = classify(token)
        if citation.bucket == "unknown":
            if citation.code not in page.unknown_tokens:
                page.unknown_tokens.append(citation.code)
            return
        if citation.code in seen:
            return
        seen.add(citation.code)
        page.citations.append(
            Citation(code=token, href=href, origin=origin)
        )

    # Novel codes are trustworthy from the href alone, anywhere in the article.
    for anchor in A_RE.finditer(article):
        href = anchor.group("href")
        if "/source/" not in href:
            continue
        derived = _derive_code_from_href(href)
        if derived is not None:
            record(derived, href, "href")
        else:
            text = _strip_tags(anchor.group("text")).strip()
            if _is_codeish(text):
                record(text, href, "anchor")

    # Bare parenthesials inside references sections cover non-novel sources.
    for group in PAREN_RE.findall(_strip_tags(refs_html)):
        for token in (part.strip() for part in group.split(",")):
            if _is_codeish(token):
                record(token, None, "bare")

    groups: dict[str, int] = {}
    for rel in RELATEDLINK_RE.finditer(html):
        group = rel.group("group")
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
            (rel.group("group"), _strip_tags(rel.group("text")).strip(), rel.group("href"))
        )
    return page
