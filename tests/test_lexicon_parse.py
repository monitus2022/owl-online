"""Tests for the spike Lexicon parsers on synthetic fixtures.

The fixtures mirror the observed WordPress structure of hp-lexicon.org (see
docs/lexicon-canon-index.md, Site anatomy) with entirely invented placeholder
text. Scraped pages must never enter git, so the tests exercise the markup
skeleton, not the site.
"""

import pytest

from app.pipeline.ingest.lexicon.parse import parse_chapter_page, parse_entry_page

ENTRY_URL = "https://www.hp-lexicon.org/magic/summoning-charm/"

ENTRY_HTML = """
<html><body>
<h1>Raising Charm</h1>
<div class="data">Magic Type <span>
    <a href="https://www.hp-lexicon.org/magictype/charms/">Charms</a>
    <a href="https://www.hp-lexicon.org/magictype/movement/">Movement</a>
</span></div>
<div class="data">Incantation <span>Assurgo</span></div>
<div class="data">Pronunciation <span>a-SUR-go</span></div>
<h2>History and Notes</h2>
<p>Invented placeholder prose about the charm.</p>
<h2>References from the canon</h2>
<ul>
<li>The student raised a feather in the first class
(<a href="/source/the-harry-potter-novels/ss/ss6">PS6</a>).</li>
<li>The pupil practised on chairs
(<a href="/source/the-harry-potter-novels/gf/gf20">GF20</a>).
She rehearsed daily.</li>
<li>A shopkeeper used it offscreen
(<a href="/source/films-and-plays/cg">CG48</a>).</li>
<li>Twin objects were recalled at once
(<a href="/source/the-harry-potter-novels/dh/dh10">DH10</a>,
<a href="/source/the-harry-potter-novels/dh/dh26">DH26</a>).</li>
<li>A companion volume notes the counter-enchantment (BoS4).</li>
<li>A film-only usage exists (CS/f).</li>
<li>Something cites (Mystery9), an unknown abbreviation.</li>
</ul>
<div class="related_container">
<div class="panel-body">
<div class="relatedlink-container relatedlink-magic">
    <a class="relatedlink related-magic" href="/magic/other-spell/">Other Spell</a>
</div>
<div class="relatedlink-container relatedlink-thing">
    <a class="relatedlink related-thing" href="/thing/feather/">Feather</a>
</div>
</div>
</div>
</body></html>
"""

CHAPTER_URL = "https://www.hp-lexicon.org/source/the-harry-potter-novels/gf/gf6/"

CHAPTER_HTML = """
<html><body>
<h1>The Portkey Field</h1>
<div class="data">Author <span>F. Author</span></div>
<div class="data">Abbreviation <span>GF6: The Portkey Field</span></div>
<div class="data">Canonicity <span>Primary Canon</span></div>
<div class="related_container">
<div class="relatedlink-container relatedlink-magic">
    <a class="relatedlink related-magic" href="/magic/summoning-charm/">Summoning Charm</a>
</div>
<div class="relatedlink-container relatedlink-character">
    <a class="relatedlink related-character" href="/character/x/">A Person</a>
</div>
</div>
</body></html>
"""


def test_entry_page_identity_and_info_lines():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert page.title == "Raising Charm"
    assert page.incantation == "Assurgo"
    assert page.magic_types == ["Charms", "Movement"]
    assert page.has_references_section


def test_linked_and_bare_citations_are_all_harvested():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    codes = {c.code: c.origin for c in page.citations}
    assert codes["GF20"] == "references"
    assert codes["BoS4"] == "bare"
    assert codes["CS/f"] == "bare"
    assert codes["CG48"] == "references"


def test_multi_code_bullet_yields_one_edge_per_code():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    dh_codes = [c.code for c in page.citations if c.code.startswith("DH")]
    assert dh_codes == ["DH10", "DH26"]
    bullets = {c.code: c.bullet for c in page.citations}
    assert bullets["DH10"] == bullets["DH26"]


def test_linked_codes_are_not_double_counted_from_the_parens():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert sum(1 for c in page.citations if c.code == "GF20") == 1


def test_unknown_codes_queue_for_review_instead_of_silence():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert "Mystery9" in page.bare_code_candidates
    assert all(c.code != "Mystery9" for c in page.citations)


def test_related_tabs_are_counted_by_group():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert page.related_groups == {"magic": 1, "thing": 1}


def test_chapter_page_identity_and_reverse_index():
    page = parse_chapter_page(CHAPTER_HTML, CHAPTER_URL)
    assert page.code == "GF"
    assert page.chapter_num == 6
    assert not page.is_epilogue
    assert page.abbreviation == "GF6: The Portkey Field"
    assert page.canonicity == "Primary Canon"
    charm = ("magic", "Summoning Charm", "/magic/summoning-charm/")
    assert charm in page.related


def test_epilogue_chapter_page_is_flagged():
    page = parse_chapter_page(
        CHAPTER_HTML, "https://www.hp-lexicon.org/source/the-harry-potter-novels/dh/dhe/"
    )
    assert page.code == "DH"
    assert page.is_epilogue
    assert page.chapter_num is None


def test_non_novel_source_url_fails_loudly():
    with pytest.raises(ValueError):
        parse_chapter_page(CHAPTER_HTML, "https://www.hp-lexicon.org/source/other-canon/pm/pm1/")
