"""Contract/authority routing fixture (#217).

Each item records the answer contract, the gold fact IDs and whether a
supporting fact exists. The fixture is frozen before cue tuning; items marked
``holdout`` are not for cue tuning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CONTRACTS = frozenset(
    {"policy", "persona", "lore", "lesson", "abstain", "clarify"}
)
SUBJECTS = ("dada", "charms", "potions", "transfiguration", "herbology")
FACT_PREFIX = {
    "policy": "policy:",
    "persona": "persona:",
    "lore": "lore:",
    "lesson": "lesson:",
}
REQUIRED_UTTERANCES = frozenset(
    {
        "where did you study when you are young",
        "what is included in dada?",
    }
)
MINIMUMS = {
    "policy": 30,
    "persona": 25,
    "lore": 15,
    "lesson": 30,
    "abstain": 15,
    "clarify": 10,
}


@dataclass(frozen=True)
class RoutingItem:
    item_id: str
    utterance: str
    contract: str
    fact_ids: tuple[str, ...]
    fact_present: bool
    category: str
    holdout: bool = False
    note: str = ""
    subject: str = "dada"

    def fact_prefix_ok(self) -> bool:
        if self.contract in FACT_PREFIX:
            prefix = FACT_PREFIX[self.contract]
            return all(fact_id.startswith(prefix) for fact_id in self.fact_ids)
        if self.contract == "clarify":
            return all(
                fact_id.startswith(("policy:", "persona:", "lore:", "lesson:"))
                for fact_id in self.fact_ids
            )
        return not self.fact_ids


def _require_str(record: dict[str, object], key: str, where: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: missing or empty {key!r}")
    return value.strip()


def _fact_ids(record: dict[str, object], where: str) -> tuple[str, ...]:
    value = record.get("fact_ids", [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{where}: fact_ids must be a list of non-empty strings")
    return tuple(item.strip() for item in value)


def parse_item(record: dict[str, object], where: str) -> RoutingItem:
    item_id = _require_str(record, "id", where)
    utterance = _require_str(record, "utterance", where)
    contract = _require_str(record, "contract", where)
    if contract not in CONTRACTS:
        raise ValueError(f"{where}: unknown contract {contract!r}")
    category = _require_str(record, "category", where)
    subject = record.get("subject", "dada")
    if not isinstance(subject, str) or subject not in SUBJECTS:
        raise ValueError(f"{where}: unknown subject {subject!r}")
    fact_ids = _fact_ids(record, where)
    fact_present = record.get("fact_present")
    if not isinstance(fact_present, bool):
        raise ValueError(f"{where}: fact_present must be a boolean")
    holdout = record.get("holdout", False)
    if not isinstance(holdout, bool):
        raise ValueError(f"{where}: holdout must be a boolean")
    note = record.get("note", "")
    if not isinstance(note, str):
        raise ValueError(f"{where}: note must be a string")
    item = RoutingItem(
        item_id=item_id,
        utterance=utterance,
        contract=contract,
        subject=subject,
        fact_ids=fact_ids,
        fact_present=fact_present,
        category=category,
        holdout=holdout,
        note=note.strip(),
    )
    if not item.fact_prefix_ok():
        raise ValueError(
            f"{where}: fact ids do not match contract {contract!r}: {fact_ids}"
        )
    if fact_present != bool(fact_ids):
        raise ValueError(
            f"{where}: fact_present must equal whether fact_ids is non-empty"
        )
    return item


def load_routing_items(path: Path) -> list[RoutingItem]:
    items: list[RoutingItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path}:{line_number}"
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{where}: invalid JSON: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{where}: each line must be an object")
        item = parse_item(record, where)
        if item.item_id in seen:
            raise ValueError(f"{where}: duplicate id {item.item_id!r}")
        seen.add(item.item_id)
        items.append(item)
    if not items:
        raise ValueError(f"{path}: no routing items")
    return items


def validate_fixture(items: list[RoutingItem]) -> None:
    """Shape, coverage and holdout checks; run in tests, not at import."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.contract] = counts.get(item.contract, 0) + 1
    missing = {
        contract: minimum
        for contract, minimum in MINIMUMS.items()
        if counts.get(contract, 0) < minimum
    }
    if missing:
        raise ValueError(f"fixture is missing contract coverage: {missing}")
    def normalise(text: str) -> str:
        return text.lower().strip().rstrip("?.!")

    utterances = {normalise(item.utterance) for item in items}
    absent = {normalise(text) for text in REQUIRED_UTTERANCES} - utterances
    if absent:
        raise ValueError(f"fixture is missing required utterances: {sorted(absent)}")
    if not any(item.holdout for item in items):
        raise ValueError("fixture needs at least one held-out paraphrase family")
    if any(item.contract == "lesson" and item.fact_present is False for item in items):
        raise ValueError("lesson items must record a supporting lesson fact")
    if any(
        item.contract in {"persona", "lore"} and not item.fact_present
        for item in items
    ):
        raise ValueError("persona and lore items must record a supporting fact")


def validate_subject_fixture(items: list[RoutingItem]) -> None:
    """Per-subject coverage for the five-card routing fixture (#222)."""
    by_subject: dict[str, list[RoutingItem]] = {}
    for item in items:
        by_subject.setdefault(item.subject, []).append(item)
    missing = set(SUBJECTS) - set(by_subject)
    if missing:
        raise ValueError(f"subject fixture is missing subjects: {sorted(missing)}")
    for subject, rows in by_subject.items():
        contracts = {row.contract for row in rows}
        absent = CONTRACTS - contracts
        if absent:
            raise ValueError(f"{subject}: missing contracts {sorted(absent)}")
        if len(rows) < 10:
            raise ValueError(f"{subject}: needs at least 10 items")
        if not any(row.holdout for row in rows):
            raise ValueError(f"{subject}: needs a held-out item")
        required = f"what is included in {subject}"
        clarify_rows = [
            row
            for row in rows
            if row.utterance.lower().rstrip("?.!") == required
        ]
        if not clarify_rows:
            raise ValueError(f"{subject}: missing {required!r}")
        if any(row.contract != "clarify" for row in clarify_rows):
            raise ValueError(f"{subject}: {required!r} must be a clarify item")
        if any(
            row.contract in {"persona", "lore", "lesson"} and not row.fact_present
            for row in rows
        ):
            raise ValueError(f"{subject}: persona/lore/lesson items need a fact")


def validate_paraphrase_fixture(items: list[RoutingItem]) -> None:
    """Setting-phrasing coverage for #327.

    ``lore`` with ``fact_present`` false is deliberate: the utterance is a
    setting question, no entry covers it, and any selected entry is a stretch.
    """
    if len(items) < 60:
        raise ValueError("paraphrase fixture needs at least 60 items")
    if not any(item.holdout for item in items):
        raise ValueError("paraphrase fixture needs a holdout split")
    if any(item.contract not in {"lore", "clarify"} for item in items):
        raise ValueError("paraphrase items must be lore or clarify")
    clarify = [item for item in items if item.contract == "clarify"]
    if len(clarify) < 8:
        raise ValueError("paraphrase fixture needs at least 8 multi-intent items")
    no_fact = [
        item for item in items if item.contract == "lore" and not item.fact_present
    ]
    if len(no_fact) < 6:
        raise ValueError("paraphrase fixture needs at least 6 no-fact items")
    if any(
        item.fact_present and not item.fact_ids[0].startswith("lore:")
        for item in items
    ):
        raise ValueError("paraphrase lore facts must use the lore: prefix")
    if any(item.contract == "lore" and item.fact_present and not item.fact_ids for item in items):
        raise ValueError("a lore item with a fact must name the entry")
    utterances = [item.utterance.casefold().strip().rstrip("?.!") for item in items]
    if len(utterances) != len(set(utterances)):
        raise ValueError("paraphrase fixture contains a duplicate utterance")


def validate_must_not_fixture(items: list[RoutingItem]) -> None:
    """Book questions that carry setting words; any lore route is a false positive."""
    if len(items) < 30:
        raise ValueError("must_not fixture needs at least 30 items")
    if not any(item.holdout for item in items):
        raise ValueError("must_not fixture needs a holdout split")
    if any(item.contract != "lesson" for item in items):
        raise ValueError("must_not items are book questions in a lesson room")
    if any(item.fact_present or item.fact_ids for item in items):
        raise ValueError("must_not items must not carry a teaching fact")


@dataclass(frozen=True)
class MultiturnItem:
    """A short conversation whose final turn is the routing target."""

    item_id: str
    turns: tuple[str, ...]
    final_contract: str
    final_fact_ids: tuple[str, ...]
    fact_present: bool
    holdout: bool = False
    subject: str = "dada"
    note: str = ""

    def fact_prefix_ok(self) -> bool:
        if self.final_contract in FACT_PREFIX:
            prefix = FACT_PREFIX[self.final_contract]
            return all(fact.startswith(prefix) for fact in self.final_fact_ids)
        return True


def load_multiturn_items(path: Path) -> list[MultiturnItem]:
    items: list[MultiturnItem] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path}:{line_number}"
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{where}: invalid JSON: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{where}: each line must be an object")
        item_id = _require_str(record, "id", where)
        if item_id in seen:
            raise ValueError(f"{where}: duplicate id {item_id!r}")
        seen.add(item_id)
        turns = record.get("turns")
        if (
            not isinstance(turns, list)
            or len(turns) < 2
            or not all(isinstance(turn, str) and turn.strip() for turn in turns)
        ):
            raise ValueError(f"{where}: turns must be a list of at least two strings")
        contract = _require_str(record, "final_contract", where)
        if contract not in CONTRACTS:
            raise ValueError(f"{where}: unknown contract {contract!r}")
        subject = record.get("subject", "dada")
        if not isinstance(subject, str) or subject not in SUBJECTS:
            raise ValueError(f"{where}: unknown subject {subject!r}")
        final_fact_ids = record.get("final_fact_ids", [])
        if not isinstance(final_fact_ids, list) or not all(
            isinstance(item, str) and item.strip() for item in final_fact_ids
        ):
            raise ValueError(
                f"{where}: final_fact_ids must be a list of non-empty strings"
            )
        fact_ids = tuple(item.strip() for item in final_fact_ids)
        if fact_ids:
            if contract not in FACT_PREFIX:
                raise ValueError(f"{where}: {contract!r} cannot carry fact ids")
        fact_present = record.get("fact_present")
        if not isinstance(fact_present, bool) or fact_present != bool(fact_ids):
            raise ValueError(f"{where}: fact_present must equal whether fact_ids is non-empty")
        holdout = record.get("holdout", False)
        if not isinstance(holdout, bool):
            raise ValueError(f"{where}: holdout must be a boolean")
        note = record.get("note", "")
        if not isinstance(note, str):
            raise ValueError(f"{where}: note must be a string")
        item = MultiturnItem(
            item_id=item_id,
            turns=tuple(turn.strip() for turn in turns),
            final_contract=contract,
            final_fact_ids=fact_ids,
            fact_present=fact_present,
            holdout=holdout,
            subject=subject,
            note=note.strip(),
        )
        if not item.fact_prefix_ok():
            raise ValueError(f"{where}: fact ids do not match contract {contract!r}")
        items.append(item)
    if not items:
        raise ValueError(f"{path}: no multiturn items")
    return items


def validate_multiturn_fixture(items: list[MultiturnItem]) -> None:
    if len(items) < 20:
        raise ValueError("multiturn fixture needs at least 20 conversations")
    if not any(item.holdout for item in items):
        raise ValueError("multiturn fixture needs a holdout split")
    if any(len(item.turns) < 2 for item in items):
        raise ValueError("every multiturn item needs a follow-up")
    seen: set[tuple[str, ...]] = set()
    for item in items:
        key = tuple(turn.casefold() for turn in item.turns)
        if key in seen:
            raise ValueError(f"duplicate conversation {item.item_id}")
        seen.add(key)


__all__ = [
    "CONTRACTS",
    "MINIMUMS",
    "REQUIRED_UTTERANCES",
    "SUBJECTS",
    "MultiturnItem",
    "RoutingItem",
    "load_multiturn_items",
    "load_routing_items",
    "parse_item",
    "validate_fixture",
    "validate_must_not_fixture",
    "validate_multiturn_fixture",
    "validate_paraphrase_fixture",
    "validate_subject_fixture",
]
