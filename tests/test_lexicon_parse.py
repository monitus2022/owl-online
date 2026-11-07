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
<p>Invented placeholder prose about the charm
(<a href="/source/the-harry-potter-novels/op/op35">OP35</a>).</p>
<h2>References from the canon</h2>
<ul>
<li>The student raised a feather in the first class
(<a href="/source/the-harry-potter-novels/ps/ps6">PS6</a>).</li>
<li>The pupil practised on chairs
(<a href="/source/the-harry-potter-novels/gf/gf20">GF20</a>).
She rehearsed daily (<a href="/source/the-harry-potter-novels/gf/gf20">GF20</a>).</li>
<li>A shopkeeper used it offscreen
(<a href="/source/films-and-plays/cg">CG48</a>).</li>
<li>Twin objects were recalled at once
(<a href="/source/the-harry-potter-novels/dh/dh10">DH10</a>,
<a href="/source/the-harry-potter-novels/dh/dh26">DH26</a>).</li>
<li>A companion volume notes the counter-enchantment (BoS4).</li>
<li>A film-only usage exists (CS/f).</li>
<li>Pottermore repeats it (Pm).</li>
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
<div class="site-footer">
<a href="/source/the-harry-potter-novels/gf/gf9/">9</a>
<a href="/source/the-harry-potter-novels/gf/gf10/">10</a>
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
    <a class="relatedlink related-characters" href="/character/x/">A Person</a>
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


def test_novel_codes_are_derived_from_the_href_anywhere_in_the_article():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    books = {c.code for c in page.citations if c.origin == "href"}
    assert {"PS6", "GF20", "DH10", "DH26", "OP35"} <= books


def test_prose_citation_outside_the_references_section_is_harvested():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert any(c.code == "OP35" for c in page.citations)


def test_linked_non_novel_and_bare_parenthetical_citations():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    codes = {c.code: c.origin for c in page.citations}
    assert codes["CG48"] == "anchor"
    assert codes["BoS4"] == "bare"
    assert codes["CS/f"] == "bare"
    assert codes["Pm"] == "bare"


def test_multi_code_novel_bullet_yields_one_edge_per_code():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    dh_codes = [c.code for c in page.citations if c.code.startswith("DH")]
    assert dh_codes == ["DH10", "DH26"]


def test_repeated_code_is_deduplicated():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert sum(1 for c in page.citations if c.code == "GF20") == 1


def test_site_footer_chapter_nav_is_not_scanned():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert not any(c.code in {"GF9", "GF10"} for c in page.citations)


def test_unknown_codes_queue_for_review_instead_of_silence():
    page = parse_entry_page(ENTRY_HTML, ENTRY_URL)
    assert "Mystery9" in page.unknown_tokens
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
    # plural tab names normalise: the crawl shows `related-characters`
    assert ("character", "A Person", "/character/x/") in page.related


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


def test_paragraph_style_references_and_heading_variant():
    """Observed in the #125 sample: sectumsempra uses <p> blocks; the
    Animagus page names the section 'Canon references'."""
    html = """
    <html><body><h1>Curse Example</h1>
    <h2>Canon references</h2>
    <p>Used by a villain against a target
    (<a href="/source/the-harry-potter-novels/hbp/hbp21">HBP21</a>).</p>
    <p>A companion book lists it as dark (BoS16).</p>
    <div class="related_container"></div>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/curse-example/")
    assert page.has_references_section
    codes = {c.code: c.origin for c in page.citations}
    assert codes["HBP21"] == "href"
    assert codes["BoS16"] == "bare"


def test_bare_citations_outside_any_references_section_are_still_harvested():
    """Observed in the #125 sample: Corporeal Patronus has no references
    heading but carries (Pm) and (JKR:Tw) in prose."""
    html = """
    <html><body><h1>Corporeal Guardian</h1>
    <p>Wizard A conjured a corporeal guardian in year five (JKR:Tw),
    and the form was recorded on the companion website (Pm).
    The name of the charm was noted (Molly).</p>
    <div class="related_container"></div>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/corporeal-patronus/")
    codes = {c.code for c in page.citations}
    assert {"JKR:Tw", "Pm"} <= codes
    # Prose parenthesials are not queued as unknown codes.
    assert page.unknown_tokens == []


def test_multi_code_list_splits_on_and():
    html = """
    <html><body><h1>Paired Hex</h1>
    <p>Seen twice (PS1 and PS2).</p>
    <div class="related_container"></div>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/paired-hex/")
    assert {c.code for c in page.citations} == {"PS1", "PS2"}


def test_entry_page_without_the_region_boundary_fails_loudly():
    html = (
        "<html><body><h1>No Boundary</h1>"
        '<a href="/source/the-harry-potter-novels/gf/gf9/">9</a>'
        "</body></html>"
    )
    with pytest.raises(ValueError):
        parse_entry_page(html, "https://www.hp-lexicon.org/magic/no-boundary/")


def test_prose_parenthesials_do_not_crash_the_bare_scan():
    """Observed in the #126 full crawl: `(and the cure)` splits to an empty
    token, and `("Crucio")` arrives entity-encoded; neither may raise."""
    html = """
    <html><body><h1>Curse</h1>
    <p>Cast (and the cure) said &#8220;Crucio&#8221; (GF34).</p>
    <div class="related_container"></div>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/curse/")
    assert {c.code for c in page.citations} == {"GF34"}
    assert page.unknown_tokens == []


def test_thin_entry_falls_back_to_the_footer_stop():
    """Observed in the #126 smoke run: thin thing-entries have no Related
    container; the region then ends at the footer instead of raising."""
    html = """
    <html><body><h1>Sweet</h1>
    <p>A sweet mentioned once (<a href="/source/the-harry-potter-novels/hbp/hbp25">HBP25</a>).</p>
    <footer><a href="/source/the-harry-potter-novels/gf/gf11/">11</a></footer>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/thing/sweet/")
    assert any(c.code == "HBP25" for c in page.citations)
    assert not any(c.code == "GF11" for c in page.citations)


def test_citations_carry_their_parse_time_resolution():
    """The bucket comes from where the code was found (href fallback), not a
    later re-classification of the bare code."""
    html = """
    <html><body><h1>Beast</h1>
    <div class="related_container"></div>
    <span> Sources</span>
      <a href=".../source/films-and-plays/fbf/">Fantastic Beasts (film series)</a>
    <div>The Harry Potter Canon</div>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/creature/murtlap/")
    row = [c for c in page.citations if c.code == "FBF"]
    assert len(row) == 1
    assert row[0].resolved.bucket == "excluded"


def test_unlinked_anchor_is_bucketed_from_its_source_url_path():
    """Observed in the #125 queue: BCE, PmP, WSch label prose links that carry
    no recognisable abbreviation; the /source/ path resolves them."""
    html = """
    <html><body><h1>Transfiguration Note</h1>
    <p>A leaf from a mandrake is carried for a month
    (<a href="https://www.hp-lexicon.org/source/other-canon/bce/">this essay</a>).</p>
    <div class="related_container"></div>
    </body></html>
    """
    page = parse_entry_page(
        html, "https://www.hp-lexicon.org/magic/animagus-transfiguration/"
    )
    codes = {c.code: c.origin for c in page.citations}
    assert codes == {"BCE": "anchor"}


def test_sidebar_sources_are_scanned_and_stay_a_separate_origin():
    """The page-level Sources widget repeats novel codes; origin=sidebar keeps
    them apart from article codes so #127 can score the agreement."""
    html = """
    <html><body><h1>Summoning Thing</h1>
    <p>Cited in the article (<a href="/source/the-harry-potter-novels/gf/gf20">GF20</a>).</p>
    <div class="related_container"></div>
    <div class="sidebar"><span> Sources</span>
      <a href="/source/the-harry-potter-novels/gf/gf20">Chapter 20</a>
      <a href="/source/other-canon/bos/">The Book of Spells</a>
    </div>
    <div>The Harry Potter Canon site-wide nav</div>
    <a href="/source/the-harry-potter-novels/ps/ps1/">1</a>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/summoning-thing/")
    assert page.sidebar_scanned
    sidebar = {(c.code, c.origin) for c in page.citations if c.origin == "sidebar"}
    assert ("GF20", "sidebar") in sidebar
    assert ("BoS", "sidebar") in sidebar
    # The site-wide footer nav after the stop marker is never scanned.
    assert not any(c.code == "PS1" for c in page.citations)


def test_sidebar_is_skipped_without_a_stop_marker():
    html = """
    <html><body><h1>Odd Layout</h1>
    <p>No references here.</p>
    <div class="related_container"></div>
    <span> Sources</span><a href="/source/the-harry-potter-novels/gf/gf11/">11</a>
    </body></html>
    """
    page = parse_entry_page(html, "https://www.hp-lexicon.org/magic/odd-layout/")
    assert not page.sidebar_scanned
    assert not any(c.code == "GF11" for c in page.citations)
