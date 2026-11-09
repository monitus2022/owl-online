"""Tests for the Charms authoring quote reconstruction (#128)."""

from __future__ import annotations

import pytest

from app.knowledge.materials import Material, SourceRef
from scripts.author_charms import _is_sentence_end, _review_status, quote_for


def _material() -> Material:
    ref = SourceRef(
        chunk_id="b1-c10-0029",
        book=1,
        chapter=10,
        quote="swish and flick",
        text_hash="abc123",
        index_text_hash="def456",
    )
    return Material(
        material_id="charms-test",
        subject="charms",
        topic="charms-foundations",
        concept="charms-definition-charm",
        kind="definition",
        text="A grounded test material.",
        source_refs=[ref],
        review_status="reviewed",
    )


def test_review_status_survives_only_an_identical_material() -> None:
    previous = _material()
    assert (
        _review_status(
            previous,
            text=previous.text,
            topic=previous.topic,
            concept=previous.concept,
            kind=previous.kind,
            refs=previous.source_refs,
            references=previous.references,
        )
        == "reviewed"
    )
    changed_ref = previous.source_refs[0].model_copy(
        update={"quote": "a different quote"}
    )
    assert (
        _review_status(
            previous,
            text=previous.text,
            topic=previous.topic,
            concept=previous.concept,
            kind=previous.kind,
            refs=[changed_ref],
            references=previous.references,
        )
        == "draft"
    )
    assert (
        _review_status(
            previous,
            text="Changed prose.",
            topic=previous.topic,
            concept=previous.concept,
            kind=previous.kind,
            refs=previous.source_refs,
            references=previous.references,
        )
        == "draft"
    )


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
