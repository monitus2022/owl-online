"""Sparse-leg tokenizer: the pinned regex choice."""

from app.pipeline.index.builder import TOKENIZER, tokenize


def test_tokenizer_is_pinned():
    assert TOKENIZER == "regex-words"


def test_case_and_punctuation_are_normalized():
    assert tokenize("Rowan's, wick!") == ["rowan's", "wick"]
    assert tokenize("Bypassed") == ["bypassed"]


def test_stemming_is_not_applied():
    # #79 measured Snowball+: sparse recall rose but Hit@5 fell, so the pinned
    # tokenizer deliberately keeps inflected forms apart.
    assert tokenize("bypassed") != tokenize("bypass")
