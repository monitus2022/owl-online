"""Gold set shape tests, no network."""

from collections import Counter
from pathlib import Path

from eval.harness import load_gold

GOLD_PATH = Path(__file__).with_name("gold") / "questions.jsonl"


def test_gold_set_keeps_the_pinned_shape():
    items = load_gold(GOLD_PATH)
    assert len(items) == 60
    assert sum(item.answerable for item in items) == 50
    assert sum(not item.answerable for item in items) == 10

    slices = Counter(label for item in items for label in item.slices)
    assert slices == {
        "simple": 34,
        "named_reference": 8,
        "multi_part": 8,
        "near_miss_unanswerable": 5,
        "off_topic": 5,
    }


def test_every_item_carries_what_its_slice_needs():
    items = load_gold(GOLD_PATH)
    assert all(item.reference_answer for item in items if item.answerable)
    assert all(item.expected_chunk_ids for item in items if item.answerable)
    assert all(item.reason for item in items if not item.answerable)
