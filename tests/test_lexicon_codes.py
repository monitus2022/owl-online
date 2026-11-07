"""Tests for the spike citation-code grammar (docs/lexicon-canon-index.md)."""

import pytest

from app.pipeline.ingest.lexicon.codes import (
    BUCKET_BOOKS,
    BUCKET_EXCLUDED,
    BUCKET_SECONDARY,
    BUCKET_UNKNOWN,
    chapter_is_valid,
    classify,
)


def test_novel_chapter_code_maps_to_corpus_book_and_chapter():
    resolved = classify("GF6")
    assert resolved.bucket == BUCKET_BOOKS
    assert (resolved.book_num, resolved.chapter_num) == (4, 6)
    assert resolved.usable_for_packs


def test_half_blood_prince_code_beats_potential_prefixes():
    resolved = classify("HBP26")
    assert (resolved.book_num, resolved.chapter_num) == (6, 26)
    assert classify("HP8").bucket == BUCKET_UNKNOWN


def test_epilogue_code_resolves_to_book_seven_flagged_as_epilogue():
    resolved = classify("DHE")
    assert resolved.bucket == BUCKET_BOOKS
    assert resolved.book_num == 7
    assert resolved.is_epilogue
    # The epilogue edge is distinct from a plain chapter-36 citation.
    assert not classify("DH36").is_epilogue


def test_epilogue_film_suffix_is_excluded():
    resolved = classify("DHE/f")
    assert resolved.bucket == BUCKET_EXCLUDED
    assert resolved.medium == "film"
    assert not resolved.usable_for_packs


def test_whole_book_code_has_no_chapter():
    resolved = classify("OP")
    assert resolved.bucket == BUCKET_BOOKS
    assert resolved.book_num == 5
    assert resolved.chapter_num is None


def test_secondary_book_codes_are_recorded_not_books():
    for code, chapter in [("QA4", 4), ("BoS4", 4), ("FB", None), ("TBB", None)]:
        resolved = classify(code)
        assert resolved.bucket == BUCKET_SECONDARY, code
        assert resolved.book_num is None, code
        assert resolved.chapter_num == chapter, code
        assert not resolved.usable_for_packs


def test_screenplay_and_other_canon_are_excluded():
    for code in ["WFT", "CG48", "SD", "CC", "PM", "Pm", "JKR:Tw", "DP", "MagSp"]:
        resolved = classify(code)
        assert resolved.bucket == BUCKET_EXCLUDED, code
        assert not resolved.usable_for_packs


def test_decimal_scene_codes_stay_excluded_and_chapterless():
    resolved = classify("CC3.9")
    assert resolved.bucket == BUCKET_EXCLUDED
    assert resolved.chapter_num is None


def test_film_and_game_suffixes_never_land_in_books():
    film = classify("CS/f")
    assert film.bucket == BUCKET_EXCLUDED
    assert film.medium == "film"
    assert film.book_num == 2
    assert film.chapter_num is None
    game = classify("PA5/g")
    assert game.bucket == BUCKET_EXCLUDED
    assert game.medium == "game"
    assert (game.book_num, game.chapter_num) == (3, 5)


def test_unknown_codes_are_queued_not_dropped():
    resolved = classify("ZZZ9")
    assert resolved.bucket == BUCKET_UNKNOWN
    assert resolved.code == "ZZZ9"


def test_tale_level_beedle_codes_are_secondary_books():
    for code in ["TBB/BR", "TBB/WHH"]:
        resolved = classify(code)
        assert resolved.bucket == BUCKET_SECONDARY, code
        assert not resolved.usable_for_packs


def test_source_href_fallback_buckets_unknown_abbreviations_by_path():
    from app.pipeline.ingest.lexicon.codes import classify_source_href

    # Path slugs resolve codes the abbreviation table may not even know.
    bce = classify_source_href("https://www.hp-lexicon.org/source/other-canon/bce/")
    assert bce.bucket == BUCKET_EXCLUDED and bce.code == "BCE"
    # A companion-book path is secondary, in the table's own casing.
    bos = classify_source_href("https://www.hp-lexicon.org/source/other-canon/bos/")
    assert bos.bucket == BUCKET_SECONDARY and bos.code == "BoS"
    # A bare novel root is a book-level edge with no chapter.
    gf = classify_source_href("https://www.hp-lexicon.org/source/the-harry-potter-novels/gf/")
    assert gf.bucket == BUCKET_BOOKS and gf.book_num == 4 and gf.chapter_num is None
    # A tale page under the TBB tree.
    tale = classify_source_href("https://www.hp-lexicon.org/source/other-potter-books/tbb/tbbbr")
    assert tale.bucket == BUCKET_SECONDARY and tale.code == "TBB/BR"
    assert classify_source_href("https://www.hp-lexicon.org/magic/accio/") is None


def test_empty_code_fails_loudly():
    with pytest.raises(ValueError):
        classify("   ")


def test_chapter_bounds_follow_the_corpus():
    assert chapter_is_valid(classify("GF37"))
    assert not chapter_is_valid(classify("GF38"))
    assert not chapter_is_valid(classify("PS18"))
    assert chapter_is_valid(classify("DH"))
    assert chapter_is_valid(classify("WFT"))
