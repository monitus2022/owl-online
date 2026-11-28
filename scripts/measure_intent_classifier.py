"""Measure the #327 residual classifier on the three frozen slices.

This is the live companion to `measure_paraphrase_routing.py`: the same slices,
but the residual abstain is passed through the pinned small model and the
evidence gate. One call per residual; every other turn is deterministic.

Run:
    uv run python scripts/measure_intent_classifier.py
    uv run python scripts/measure_intent_classifier.py --mode shadow
    uv run python scripts/measure_intent_classifier.py --check
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.agent.intent import ResidualClassifier  # noqa: E402
from app.agent.memory import extract_entity, resolve_followup  # noqa: E402
from app.agent.persona import PERSONAS  # noqa: E402
from app.agent.router import route  # noqa: E402
from app.config import settings  # noqa: E402
from app.knowledge.lore import load_lore  # noqa: E402
from app.providers.factory import make_llm  # noqa: E402
from eval.routing.fixtures import (  # noqa: E402
    load_multiturn_items,
    load_routing_items,
    validate_multiturn_fixture,
    validate_must_not_fixture,
    validate_paraphrase_fixture,
)
from eval.routing.terms import teaching_terms as pack_terms  # noqa: E402

FIXTURES = REPO / "eval" / "routing" / "fixtures"
LORE_PATH = REPO / "eval" / "fixtures" / "lore"
MODE_TO_CONTRACT = {
    "fact": "lore",
    "meta": "persona",
    "policy": "policy",
    "clarify": "clarify",
    "abstain": "abstain",
    "lesson": "lesson",
    "answer": "answer",
}


ACCEPTANCE = {"used": 0, "first": 0, "second": 0, "rejected": 0}


def run_route(state: dict, intent: ResidualClassifier, mode: str) -> dict:
    payload = route(
        state,
        persona=True,
        teaching_terms=pack_terms,
        intent=intent,
        intent_mode=mode,
        lore=intent.lore,
        personas=PERSONAS,
    )
    if payload.get("classifier_used"):
        ACCEPTANCE["used"] += 1
        if "classifier_choice" not in payload:
            ACCEPTANCE["rejected"] += 1
        elif payload["classifier_choice"] == 0:
            ACCEPTANCE["first"] += 1
        else:
            ACCEPTANCE["second"] += 1
    return payload


def entry_of(payload: dict, lore, question: str, subject: str) -> str | None:
    facts = payload.get("fact_ids") or []
    if facts:
        return str(facts[0]).removeprefix("lore:")
    if payload.get("mode") == "fact":
        return None
    selected = lore.select(question, subject=subject)
    return selected[0].id if selected else None


def measure_paraphrase(
    intent: ResidualClassifier, mode: str, *, holdout: bool = False
):
    items = load_routing_items(FIXTURES / "paraphrase.jsonl")
    validate_paraphrase_fixture(items)
    if holdout:
        items = [item for item in items if item.holdout]
    correct = entry_correct = entry_total = stretched = no_fact = 0
    matrix: Counter[tuple[str, str]] = Counter()
    for item in items:
        payload = run_route(
            {
                "question": item.utterance,
                "standalone_question": item.utterance,
                "subject": item.subject,
                "requested_mode": "lesson",
                "persona_enabled": True,
            },
            intent,
            mode,
        )
        actual = MODE_TO_CONTRACT.get(str(payload["mode"]), "answer")
        matrix[(item.contract, actual)] += 1
        if actual == item.contract:
            correct += 1
        if item.fact_present:
            entry_total += 1
            picked = entry_of(payload, intent.lore, item.utterance, item.subject)
            if picked == item.fact_ids[0].removeprefix("lore:"):
                entry_correct += 1
        elif item.contract == "lore":
            no_fact += 1
            if payload.get("mode") == "fact":
                stretched += 1
    return (
        len(items),
        correct,
        entry_correct,
        entry_total,
        stretched,
        no_fact,
        matrix,
    )


def measure_must_not(
    intent: ResidualClassifier, mode: str, *, holdout: bool = False
) -> tuple[int, int]:
    items = load_routing_items(FIXTURES / "must_not.jsonl")
    validate_must_not_fixture(items)
    if holdout:
        items = [item for item in items if item.holdout]
    false_meta = 0
    for item in items:
        payload = run_route(
            {
                "question": item.utterance,
                "standalone_question": item.utterance,
                "subject": item.subject,
                "requested_mode": "lesson",
                "persona_enabled": True,
            },
            intent,
            mode,
        )
        if payload.get("mode") == "fact":
            false_meta += 1
    return len(items), false_meta


def measure_multiturn(
    intent: ResidualClassifier,
    mode: str,
    *,
    use_previous: bool = True,
    holdout: bool = False,
):
    items = load_multiturn_items(FIXTURES / "multiturn.jsonl")
    validate_multiturn_fixture(items)
    if holdout:
        items = [item for item in items if item.holdout]
    correct = entry_correct = entry_total = leaks = 0
    matrix: Counter[tuple[str, str]] = Counter()
    for item in items:
        messages: list[dict[str, str]] = []
        last_entity = last_person = last_place = None
        last_mode: str | None = None
        previous = ""
        pending = False
        resolution = None
        payload: dict = {}
        for turn in item.turns:
            resolution = resolve_followup(
                turn,
                messages=messages,
                last_entity=last_entity,
                last_person=last_person,
                last_place=last_place,
                last_mode=last_mode,
                pending_clarify=pending,
                subject=item.subject,
            )
            payload = run_route(
                {
                    "question": turn,
                    "standalone_question": resolution.standalone,
                    "last_student_message": previous if use_previous else "",
                    "forced_mode": resolution.forced_mode,
                    "preferred_mode": resolution.preferred_mode,
                    "subject": item.subject,
                    "requested_mode": "lesson",
                    "persona_enabled": True,
                },
                intent,
                mode,
            )
            last_mode = str(payload["mode"])
            resolved_entity = extract_entity(resolution.standalone)
            raw_entity = extract_entity(turn)
            entity = resolution.entity or (
                (resolved_entity or raw_entity).text
                if (resolved_entity or raw_entity) is not None
                else None
            )
            if entity is not None:
                last_entity = entity
                inferred = extract_entity(f"Tell me about {entity}")
                if inferred is not None and inferred.kind == "person":
                    last_person = entity
                if inferred is not None and inferred.kind == "place":
                    last_place = entity
            messages.append({"role": "user", "content": turn})
            previous = turn
        assert resolution is not None
        actual = MODE_TO_CONTRACT.get(last_mode or "", "answer")
        matrix[(item.final_contract, actual)] += 1
        if actual == item.final_contract:
            correct += 1
        if resolution.rule is None and (
            resolution.standalone.lower().startswith(("and ", "what about "))
            or any(
                word in resolution.standalone.lower().split()
                for word in ("it", "its", "they", "them", "this", "that", "there")
            )
        ):
            leaks += 1
        if item.fact_present and item.final_contract == "lore":
            entry_total += 1
            facts = payload.get("fact_ids") or []
            picked = str(facts[0]).removeprefix("lore:") if facts else None
            if picked == item.final_fact_ids[0].removeprefix("lore:"):
                entry_correct += 1
    return (
        len(items),
        correct,
        entry_correct,
        entry_total,
        leaks,
        matrix,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("on", "shadow"), default="on")
    parser.add_argument(
        "--no-previous",
        action="store_true",
        help="blank the student's last turn (the one-field comparison)",
    )
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    lore = load_lore(LORE_PATH)
    llm = make_llm(
        settings.intent_classifier_provider,
        model=settings.intent_classifier_model,
        temperature=0.0,
        max_tokens=64,
        timeout=settings.intent_classifier_timeout_s,
        max_attempts=0,
    )
    intent = ResidualClassifier(
        llm=llm,
        lore=lore,
        personas=PERSONAS,
        timeout_s=settings.intent_classifier_timeout_s,
    )
    print(f"model: {intent.model}")
    print(f"mode: {args.mode}")
    print(f"prompt chars (dada): {intent.prompt_chars('dada')}")

    started = time.perf_counter()
    p_total, p_correct, p_entry, p_entry_total, p_stretch, p_nofact, pmatrix = (
        measure_paraphrase(intent, args.mode, holdout=args.holdout)
    )
    m_total, m_false = measure_must_not(intent, args.mode, holdout=args.holdout)
    t_total, t_correct, t_entry, t_entry_total, t_leak, tmatrix = measure_multiturn(
        intent,
        args.mode,
        use_previous=not args.no_previous,
        holdout=args.holdout,
    )
    elapsed = time.perf_counter() - started
    latencies = intent.latencies_ms

    print(
        f"paraphrase: {p_correct}/{p_total} contract, "
        f"{p_entry}/{p_entry_total} entry, {p_stretch}/{p_nofact} stretched"
    )
    print(f"must_not: {m_false}/{m_total} false meta")
    print(
        f"multiturn: {t_correct}/{t_total} contract, "
        f"{t_entry}/{t_entry_total} entry, {t_leak}/{t_total} fragment leak"
    )
    print(f"classifier calls: {intent.calls}; wall {elapsed:.1f}s")
    print(
        "classifier acceptance: "
        f"used={ACCEPTANCE['used']} first={ACCEPTANCE['first']} "
        f"second={ACCEPTANCE['second']} rejected={ACCEPTANCE['rejected']}"
    )
    if latencies:
        ordered = sorted(latencies)
        p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
        print(
            f"latency ms: p50={statistics.median(ordered):.0f} "
            f"p95={p95:.0f} min={min(ordered):.0f} max={max(ordered):.0f}"
        )

    print("\nparaphrase matrix")
    print("| expected | actual | n |")
    print("|---|---|---:|")
    for expected in ("lore", "clarify", "policy", "persona", "lesson", "abstain"):
        for actual in ("lore", "clarify", "policy", "persona", "lesson", "abstain"):
            count = pmatrix.get((expected, actual), 0)
            if count:
                print(f"| {expected} | {actual} | {count} |")

    print("\nmultiturn matrix")
    print("| expected | actual | n |")
    print("|---|---|---:|")
    for expected in ("lore", "clarify", "policy", "persona", "lesson", "abstain"):
        for actual in ("lore", "clarify", "policy", "persona", "lesson", "abstain"):
            count = tmatrix.get((expected, actual), 0)
            if count:
                print(f"| {expected} | {actual} | {count} |")

    if args.check:
        failures: list[str] = []
        if m_false:
            failures.append(f"must_not false meta {m_false}")
        if p_correct < p_total * 0.9:
            failures.append(f"paraphrase contract {p_correct}/{p_total} below 90%")
        if t_correct < t_total * 0.5:
            failures.append(f"multiturn contract {t_correct}/{t_total} below 50%")
        if failures:
            print("\ncheck: FAIL")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print("\ncheck: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
