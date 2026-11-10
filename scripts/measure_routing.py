"""Measure the contract gates on the frozen routing fixture (#219).

This is a deterministic routing measurement: no model, no retrieval. It reports
the expected-vs-actual contract matrix, policy leaks, authority bleed and the
residual buckets. A `lesson` actual on an `abstain` item is reported as a
teaching-path residual; the lesson node still abstains when no span is found.

Run:
    uv run python scripts/measure_routing.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.agent.router import contract_decision  # noqa: E402
from eval.routing.fixtures import load_routing_items  # noqa: E402

FIXTURE = REPO / "eval" / "routing" / "fixtures" / "contracts.jsonl"
CONTRACTS = ("policy", "persona", "lore", "lesson", "abstain", "clarify")


def actual_contract(question: str, *, subject: str = "dada") -> str:
    return contract_decision(
        question, subject=subject, requested_mode="lesson"
    ).contract


def main() -> int:
    items = load_routing_items(FIXTURE)
    matrix: Counter[tuple[str, str]] = Counter()
    expected_counts: Counter[str] = Counter()
    actual_counts: Counter[str] = Counter()
    policy_leaks: list[str] = []
    authority_bleed: list[str] = []
    false_abstain: list[str] = []
    over_clarify: list[str] = []
    teaching_residual: list[str] = []

    for item in items:
        actual = actual_contract(item.utterance, subject="dada")
        matrix[(item.contract, actual)] += 1
        expected_counts[item.contract] += 1
        actual_counts[actual] += 1
        if item.contract == "policy" and actual != "policy":
            policy_leaks.append(item.item_id)
        if item.contract in {"persona", "lore"} and actual in {"lesson", "answer"}:
            authority_bleed.append(item.item_id)
        if item.contract in {"persona", "lore"} and item.fact_present and actual == "abstain":
            false_abstain.append(item.item_id)
        if item.contract != "clarify" and actual == "clarify":
            over_clarify.append(item.item_id)
        if item.contract == "abstain" and actual == "lesson":
            teaching_residual.append(item.item_id)

    print(f"items: {len(items)}")
    print("expected:", dict(expected_counts))
    print("actual:  ", dict(actual_counts))
    print()
    print("| expected | actual | n |")
    print("|---|---|---:|")
    for expected in CONTRACTS:
        for actual in CONTRACTS:
            count = matrix.get((expected, actual), 0)
            if count:
                print(f"| {expected} | {actual} | {count} |")
    print()
    print(f"policy leaks: {len(policy_leaks)} {policy_leaks}")
    print(f"authority bleed: {len(authority_bleed)} {authority_bleed}")
    print(f"false abstain (fact present): {len(false_abstain)} {false_abstain}")
    print(f"over-clarify: {len(over_clarify)} {over_clarify}")
    print(f"teaching-path residual on abstain: {len(teaching_residual)} {teaching_residual}")
    print()
    print(
        "gate:",
        "PASS" if not policy_leaks and not authority_bleed else "FAIL",
    )
    return 0 if not policy_leaks and not authority_bleed else 1


if __name__ == "__main__":
    raise SystemExit(main())
