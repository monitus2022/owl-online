"""Practice/feedback fixture shape and intent routing."""

import json
from pathlib import Path

from app.agent.router import classify

FIXTURE = Path(__file__).with_name("fixtures") / "practice_feedback.jsonl"


def test_fixture_shape_and_intents():
    items = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line]
    assert len(items) == 20
    assert sum(item["intent"] == "practice" for item in items) == 8
    assert sum(item["intent"] == "feedback" for item in items) == 12
    assert len({item["id"] for item in items}) == len(items)
    for item in items:
        assert item["question"] and item["reference_answer"]
        assert isinstance(item["expected_chunk_ids"], list)
        routed = classify(
            item["question"], student_answer=item.get("student_answer")
        )
        assert routed == item["intent"], item["id"]
        if item["intent"] == "practice":
            assert item["expected_behavior"] in {"answer", "abstain", "clarify"}
        else:
            assert item["band"] in {"strong", "partial", "wrong"}
            assert item["student_answer"]
