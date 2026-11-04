"""Question decomposition tests, no network."""

from app.pipeline.retrieve.decompose import split_question


def test_splits_a_two_part_question():
    parts = split_question(
        "What is the name of the Hogwarts gamekeeper and what kind of creature is his half-brother?"
    )
    assert parts == [
        "What is the name of the Hogwarts gamekeeper?",
        "what kind of creature is his half-brother?",
    ]


def test_keeps_a_single_question_intact():
    query = "What are the names of the two schools that visit Hogwarts?"
    assert split_question(query) == [query]


def test_does_not_split_a_between_phrase():
    query = "What is the difference between a hex and a curse?"
    assert split_question(query) == [query]


def test_caps_at_three_sub_queries():
    query = "Who is A and what is B and where is C and when is D?"
    assert len(split_question(query)) == 3
