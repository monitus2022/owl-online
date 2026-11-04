"""Metadata filter parsing tests, no network."""

from app.pipeline.retrieve.filters import MetadataFilter, parse_metadata_filter


def test_parses_numeric_book_and_chapter():
    assert parse_metadata_filter(
        "In book 3, chapter 21, what device does Hermione use?"
    ) == MetadataFilter(3, 21)


def test_parses_book_name_and_numeric_chapter():
    assert parse_metadata_filter(
        "In Prisoner of Azkaban chapter 4, who teaches Defence?"
    ) == MetadataFilter(3, 4)


def test_parses_number_words():
    assert parse_metadata_filter(
        "In book seven chapter twenty-nine, what is the diadem?"
    ) == MetadataFilter(7, 29)


def test_book_only_and_chapter_only():
    assert parse_metadata_filter("In Goblet of Fire chapter 4, what happens?") == MetadataFilter(
        4, 4
    )
    assert parse_metadata_filter("What happens in chapter 12?") == MetadataFilter(
        None, 12
    )


def test_in_world_title_filters_without_relaxing_the_floor():
    parsed = parse_metadata_filter("What is the monster in the Chamber of Secrets?")
    assert parsed == MetadataFilter(2, None)
    assert parsed is not None and parsed.explicit is False


def test_plain_question_has_no_filter():
    assert parse_metadata_filter("Who is the Potions professor?") is None


def test_chroma_where_shape():
    assert MetadataFilter(3, 21).chroma_where() == {
        "$and": [
            {"book_num": {"$eq": 3}},
            {"chapter_num": {"$eq": 21}},
        ]
    }
    assert MetadataFilter(3, None).chroma_where() == {"book_num": {"$eq": 3}}
    assert MetadataFilter(None, None).chroma_where() is None
