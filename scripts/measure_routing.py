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
from app.knowledge.packs import load_subject_pack  # noqa: E402
from app.knowledge.taxonomy import SUBJECT_NAMES  # noqa: E402
from app.knowledge.terms import content_terms  # noqa: E402
from eval.routing.fixtures import load_routing_items  # noqa: E402

FIXTURE = REPO / "eval" / "routing" / "fixtures" / "contracts.jsonl"
CONTRACTS = ("policy", "persona", "lore", "lesson", "abstain", "clarify")


def teaching_terms(subject: str) -> set[str] | None:
    path = REPO / "data" / "subjects" / subject
    if not path.exists():
        return None
    pack = load_subject_pack(path)
    terms: set[str] = set()
    terms.update(content_terms(subject))
    terms.update(content_terms(SUBJECT_NAMES.get(subject, subject)))
    for concept in pack.concepts:
        terms.update(content_terms(concept.title))
        for alias in concept.aliases:
            terms.update(content_terms(alias))
    for material in pack.materials:
        terms.update(content_terms(material.text))
    return terms


def actual_decision(
    question: str, *, subject: str = "dada", terms: set[str] | None = None
):
    return contract_decision(
        question,
        subject=subject,
        requested_mode="lesson",
        teaching_terms=terms,
    )


def main() -> int:
    items = load_routing_items(FIXTURE)
    terms = teaching_terms("dada")
    if terms is None:
        print("data/subjects/dada is missing; the teaching gate cannot be measured")
        return 2
    matrix: Counter[tuple[str, str]] = Counter()
    expected_counts: Counter[str] = Counter()
    actual_counts: Counter[str] = Counter()
    policy_leaks: list[str] = []
    authority_bleed: list[str] = []
    false_abstain: list[str] = []
    over_clarify: list[str] = []
    teaching_residual: list[str] = []
    abstain_misroute: list[str] = []
    fact_mismatch: list[str] = []

    for item in items:
        decision = actual_decision(item.utterance, subject="dada", terms=terms)
        actual = decision.contract
        matrix[(item.contract, actual)] += 1
        expected_counts[item.contract] += 1
        actual_counts[actual] += 1
        if item.contract == "policy" and actual != "policy":
            policy_leaks.append(item.item_id)
        if item.contract in {"persona", "lore"} and actual in {"lesson", "answer"}:
            authority_bleed.append(item.item_id)
        if item.contract == "lesson" and actual in {"persona", "lore", "fact"}:
            authority_bleed.append(item.item_id)
        if (
            item.contract in {"persona", "lore"}
            and item.fact_present
            and actual in {"lesson", "answer", "abstain"}
        ):
            false_abstain.append(item.item_id)
        if item.fact_ids and decision.fact_ids:
            if not set(decision.fact_ids) & set(item.fact_ids):
                fact_mismatch.append(item.item_id)
        if item.contract != "clarify" and actual == "clarify":
            over_clarify.append(item.item_id)
        if item.contract == "abstain" and actual == "lesson":
            teaching_residual.append(item.item_id)
        if item.contract == "abstain" and item.item_id != "abs-019" and actual != "abstain":
            abstain_misroute.append(item.item_id)

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
    print(f"fact mismatch: {len(fact_mismatch)} {fact_mismatch}")
    print(f"over-clarify: {len(over_clarify)} {over_clarify}")
    print(f"teaching-path residual on abstain: {len(teaching_residual)} {teaching_residual}")
    print(f"abstain misroute (excl. abs-019): {len(abstain_misroute)} {abstain_misroute}")
    print()
    gate_ok = (
        not policy_leaks
        and not authority_bleed
        and not false_abstain
        and not fact_mismatch
        and not abstain_misroute
    )
    print("gate:", "PASS" if gate_ok else "FAIL")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
