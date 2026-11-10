"""Measure the contract gates across the five subject cards (#222).

This is the per-subject companion to ``scripts/measure_routing.py``. It loads
``eval/routing/fixtures/subjects.jsonl``, the published pack for each subject
and the same deterministic gate the API uses. No model, no retrieval.

Run:
    uv run python scripts/measure_subject_routing.py
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
from eval.routing.fixtures import (  # noqa: E402
    CONTRACTS,
    load_routing_items,
    validate_subject_fixture,
)

FIXTURE = REPO / "eval" / "routing" / "fixtures" / "subjects.jsonl"


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


def main() -> int:
    items = load_routing_items(FIXTURE)
    validate_subject_fixture(items)
    terms_by_subject: dict[str, set[str]] = {}
    for subject in sorted({item.subject for item in items}):
        terms = teaching_terms(subject)
        if terms is None:
            print(f"data/subjects/{subject} is missing; cannot measure")
            return 2
        terms_by_subject[subject] = terms

    overall: Counter[tuple[str, str]] = Counter()
    policy_leaks: list[str] = []
    authority_bleed: list[str] = []
    false_abstain: list[str] = []
    fact_mismatch: list[str] = []
    over_clarify: list[str] = []
    abstain_misroute: list[str] = []

    for subject in sorted(terms_by_subject):
        rows = [item for item in items if item.subject == subject]
        matrix: Counter[tuple[str, str]] = Counter()
        for item in rows:
            decision = contract_decision(
                item.utterance,
                subject=subject,
                requested_mode="lesson",
                teaching_terms=terms_by_subject[subject],
            )
            actual = decision.contract
            matrix[(item.contract, actual)] += 1
            overall[(item.contract, actual)] += 1
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
            if item.contract == "abstain" and actual != "abstain":
                abstain_misroute.append(item.item_id)

        print(f"== {subject} ({len(rows)} items)")
        for expected in CONTRACTS:
            for actual in CONTRACTS:
                count = matrix.get((expected, actual), 0)
                if count and expected != actual:
                    print(f"  {expected} -> {actual}: {count}")

    print()
    print(f"items: {len(items)}")
    print("| expected | actual | n |")
    print("|---|---|---:|")
    for expected in CONTRACTS:
        for actual in CONTRACTS:
            count = overall.get((expected, actual), 0)
            if count:
                print(f"| {expected} | {actual} | {count} |")
    print()
    print(f"policy leaks: {len(policy_leaks)} {policy_leaks}")
    print(f"authority bleed: {len(authority_bleed)} {authority_bleed}")
    print(f"false abstain (fact present): {len(false_abstain)} {false_abstain}")
    print(f"fact mismatch: {len(fact_mismatch)} {fact_mismatch}")
    print(f"over-clarify: {len(over_clarify)} {over_clarify}")
    print(f"abstain misroute: {len(abstain_misroute)} {abstain_misroute}")
    gate_ok = (
        not policy_leaks
        and not authority_bleed
        and not false_abstain
        and not fact_mismatch
        and not over_clarify
        and not abstain_misroute
    )
    print("gate:", "PASS" if gate_ok else "FAIL")
    return 0 if gate_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
