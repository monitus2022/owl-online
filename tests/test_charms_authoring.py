"""Tests for the Charms authoring quote reconstruction (#128)."""

from __future__ import annotations

import pytest

from scripts.author_charms import _is_sentence_end, quote_for


def test_sentence_end_handles_dotted_abbreviation() -> None:
    text = "They were bound to come up in their O.W.L., and he set homework."
    period = text.index("O.W.L.") + 4
    assert _is_sentence_end(text, period) is False


def test_sentence_end_handles_lowercase_dialogue_tag() -> None:
    text = "said Levicorpus! inside his head."
    bang = text.index("!")
    assert _is_sentence_end(text, bang) is False


def test_sentence_end_handles_real_exclamation() -> None:
    text = "Aaaaaaaargh! There was a flash."
    bang = text.index("!")
    assert _is_sentence_end(text, bang) is True


def test_quote_for_expands_a_short_dialogue_fragment() -> None:
    text = 'He said, "I used Jelly-Legs. Looks as though those two should not be mixed."'
    quote = quote_for(text, "Jelly-Legs")
    assert quote in text
    assert "Jelly-Legs" in quote
    assert len(quote.split()) >= 8


def test_quote_for_does_not_stop_at_owl_abbreviation() -> None:
    text = (
        "They spent an hour reviewing Summoning Charms, which were bound to "
        "come up in their O.W.L., and he set homework."
    )
    quote = quote_for(text, "O.W.L.")
    assert quote in text
    assert quote.endswith("homework.")


def test_quote_for_missing_anchor_raises() -> None:
    with pytest.raises(ValueError):
        quote_for("a short text", "not present")
