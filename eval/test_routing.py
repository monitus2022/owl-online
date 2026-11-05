"""Routing judge parser tests."""

from eval.harness.routing import parse_routing_verdict


def test_practice_verdict_requires_all_keys():
    assert parse_routing_verdict('{"on_topic": true}', "practice") is None
    verdict = parse_routing_verdict(
        '{"on_topic": true, "grounded": true, "answerable": true, "boundary": true}',
        "practice",
    )
    assert verdict["on_topic"] is True
    assert verdict["boundary"] is True


def test_feedback_verdict_normalizes_band_and_rejects_bad_values():
    verdict = parse_routing_verdict(
        '{"band": "Partial", "error_named": true, "grounded": true, '
        '"boundary": false}',
        "feedback",
    )
    assert verdict["band"] == "partial"
    assert parse_routing_verdict(
        '{"band": "amazing", "error_named": true, "grounded": true, '
        '"boundary": false}',
        "feedback",
    ) is None
    assert parse_routing_verdict('{"band": "partial"}', "feedback") is None
