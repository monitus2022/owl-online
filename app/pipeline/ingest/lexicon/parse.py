"""Spike parsers for Lexicon entry and chapter pages.

HTML from hp-lexicon.org is regular WordPress markup. The observed anchors
(docs/lexicon-canon-index.md, Site anatomy):

- entry pages: `<h2>References from the canon</h2>` followed by a `<ul>` whose
  `<li>` items cite sources as `<a href="/source/...">GF6</a>` for the novels
  and as bare parenthesials (`(WFT)`, `(BoS4)`, `(CG48)`) otherwise;
- entry and chapter pages: `<div class="data">Label <span>value</span></div>`
  info lines (Incantation, Abbreviation, Canonicity, Magic Type links);
- both page kinds: Related Entries tabs of
  `<a class="relatedlink related-<group>" href="...">Title</a>`;
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
BULLET_RE = re.compile(r"<li>(?P<body>.*?)</li>", re.S)
PAREN_RE = re.compile(r"\(([^)]{1,40})\)")
# A parenthesised token that looks like a source code but is not in the table;
# it goes to the review queue instead of being dropped. Parenthetical prose
# carries spaces or punctuation and does not match.
CODEISH_RE = re.compile(r"[A-Za-z_/]{1,9}\d{0,3}(?:/[fg])?(?::Tw)?")
_TAG_RE = re.compile(r"<[^>]+>")

REFERENCES_HEADING = "References from the canon"


@dataclass(frozen=True)
class Citation:
    """One citation code found on an entry page, before normalisation."""

    code: str
    href: str | None
    origin: str  # references | bare
    bullet: int


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
    bare_code_candidates: list[str] = field(default_factory=list)


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


def _first_ul_after(html: str, heading: str) -> str:
    pos = html.find(heading)
    if pos == -1:
        return ""
    start = html.find("<ul", pos)
    if start == -1:
        return ""
    end = html.find("</ul>", start)
    return html[start:end] if end != -1 else html[start:]


def parse_entry_page(html: str, url: str) -> EntryPage:
    """Harvest identity, references-list citations and info lines."""
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

    refs_ul = _first_ul_after(html, REFERENCES_HEADING)
    page.has_references_section = bool(refs_ul)
    for bullet_index, li in enumerate(BULLET_RE.finditer(refs_ul)):
        body = li.group("body")
        linked = set()
        for anchor in A_RE.finditer(body):
            href = anchor.group("href")
            if "/source/" not in href:
                continue
            text = _strip_tags(anchor.group("text")).strip()
            citation = classify(text)
            if citation.bucket == "unknown":
                # An unexpected anchor label: keep it visible, do not guess.
                page.bare_code_candidates.append(f"anchor:{text}")
                continue
            linked.add(citation.code)
            page.citations.append(
                Citation(code=text, href=href, origin="references", bullet=bullet_index)
            )
        # Bare parenthesials: the site's convention for non-linked codes,
        # `(WFT)`, `(CG48)`, `(BoS4)`, including multi-code `(DH10, DH26)`.
        text_only = _strip_tags(body)
        for group in PAREN_RE.findall(text_only):
            for token in (part.strip() for part in group.split(",")):
                if not token or not CODEISH_RE.fullmatch(token):
                    continue
                citation = classify(token)
                if citation.code in linked:
                    continue
                if citation.bucket == "unknown":
                    page.bare_code_candidates.append(citation.code)
                    continue
                linked.add(citation.code)
                page.citations.append(
                    Citation(code=token, href=None, origin="bare", bullet=bullet_index)
                )

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
