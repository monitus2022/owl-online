"""Deterministic DADA bank checks (#191).

The validator is the source of truth for grounding, option rules, rubric rules,
exact duplicates and publication pins. These checks add the near-duplicate
measurement, the blueprint coverage gates and the option-length diagnostic.
"""

from __future__ import annotations

import math
import re
from itertools import combinations

from app.exam.bank import ExamBank, normalise_prompt, validate_bank
from app.knowledge.packs import SubjectPack
from app.providers.contracts import Embedder
from app.schemas import Chunk
from eval.exam.models import BankCheckReport, Check

DADA_TOPIC_TARGETS: dict[str, int] = {
    "dark-creatures": 10,
    "defensive-magic": 9,
    "dark-arts": 4,
    "dueling": 2,
}
DADA_DIFFICULTY_TARGETS: dict[str, int] = {
    "recall": 8,
    "explain_application": 12,
    "comparison_scenario": 5,
}
JACCARD_THRESHOLD = 0.75
COSINE_THRESHOLD = 0.90
ANSWER_POSITION_CAP = 0.40

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_OPTION_TEXT_RE = re.compile(r"[^a-z0-9]+")


def _sentences(text: str) -> int:
    return len([part for part in _SENTENCE_RE.split(text.strip()) if part.strip()])


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _difficulty_group(difficulty: str) -> str:
    if difficulty == "recall":
        return "recall"
    if difficulty in {"explanation", "application"}:
        return "explain_application"
    return "comparison_scenario"


def _max_jaccard(items: list) -> tuple[float, tuple[str, str] | None]:
    pairs = [
        (len(_tokens(left.prompt) & _tokens(right.prompt))
         / len(_tokens(left.prompt) | _tokens(right.prompt)),
         (left.item_id, right.item_id))
        for left, right in combinations(items, 2)
        if _tokens(left.prompt) | _tokens(right.prompt)
    ]
    if not pairs:
        return 0.0, None
    score, pair = max(pairs, key=lambda row: row[0])
    return score, pair


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


async def _max_cosine(
    items: list, embedder: Embedder
) -> tuple[float, tuple[str, str] | None]:
    vectors = await embedder.embed([item.prompt for item in items])
    pairs = [
        (_cosine(vectors[left], vectors[right]), (items[left].item_id, items[right].item_id))
        for left, right in combinations(range(len(items)), 2)
    ]
    if not pairs:
        return 0.0, None
    score, pair = max(pairs, key=lambda row: row[0])
    return score, pair


def _option_length_stats(items: list) -> tuple[float, float, int]:
    longest = 0
    gaps: list[int] = []
    for item in items:
        lengths = {
            option.option_id: len(option.text.split()) for option in item.options
        }
        correct = lengths.get(item.correct_option_id or "", 0)
        other = max(
            (length for option_id, length in lengths.items()
             if option_id != item.correct_option_id),
            default=0,
        )
        gaps.append(correct - other)
        if correct > other:
            longest += 1
    fraction = longest / len(items) if items else 0.0
    mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
    return fraction, mean_gap, len(items)


async def run_deterministic_checks(
    bank: ExamBank,
    pack: SubjectPack,
    chunks: dict[str, Chunk],
    index_text_hash: str,
    *,
    embedder: Embedder | None = None,
    target_counts: tuple[int, int] = (25, 25),
    topic_targets: dict[str, int] | None = None,
    difficulty_targets: dict[str, int] | None = None,
    material_targets: bool = True,
) -> BankCheckReport:
    """Run the deterministic checks and return the report plus measurements."""
    target_topics = DADA_TOPIC_TARGETS if topic_targets is None else topic_targets
    target_difficulty = (
        DADA_DIFFICULTY_TARGETS if difficulty_targets is None else difficulty_targets
    )
    validation = validate_bank(bank, pack, chunks, index_text_hash)
    items = list(bank.items)
    mcq_items = [item for item in items if item.kind == "mcq"]
    short_items = [item for item in items if item.kind == "short_answer"]
    counts = bank.counts()
    checks: list[Check] = []
    metrics: dict[str, object] = {
        "validation_errors": validation.errors,
        "validation_warnings": validation.warnings,
    }

    checks.append(
        Check(
            "bank_validation",
            validation.ok,
            f"errors={len(validation.errors)} warnings={len(validation.warnings)}",
            value=len(validation.errors),
        )
    )
    checks.append(
        Check(
            "counts",
            counts["mcq"] == target_counts[0]
            and counts["short_answer"] == target_counts[1],
            f"mcq={counts['mcq']} short_answer={counts['short_answer']}",
            value=counts["mcq"] + counts["short_answer"],
        )
    )

    item_errors = {
        item.item_id
        for item in items
        if any(
            error.startswith(f"{item.item_id}:")
            or error.startswith(f"{item.item_id} ")
            for error in validation.errors
            if any(
                marker in error
                for marker in (
                    "source ref",
                    "text hash",
                    "quote",
                    "chunk",
                    "material",
                    "evidence_snapshot",
                    "index hash",
                )
            )
        )
    }
    grounded = len(items) - len(item_errors)
    checks.append(
        Check(
            "grounding",
            not item_errors,
            f"{grounded}/{len(items)} items grounded",
            value=grounded,
            threshold=len(items),
        )
    )

    valid_mcq = 0
    for item in mcq_items:
        option_ids = [option.option_id for option in item.options]
        normalised = [
            _OPTION_TEXT_RE.sub(" ", option.text.lower()).strip()
            for option in item.options
        ]
        if (
            len(item.options) == 6
            and len(set(option_ids)) == len(option_ids)
            and len(set(normalised)) == len(normalised)
            and item.correct_option_id in option_ids
        ):
            valid_mcq += 1
    checks.append(
        Check(
            "mcq_options",
            valid_mcq == len(mcq_items),
            f"{valid_mcq}/{len(mcq_items)} MCQs have exactly six unique options "
            "and one key",
            value=valid_mcq,
            threshold=len(mcq_items),
        )
    )

    trivial = [
        item.item_id
        for item in mcq_items
        if any(
            _OPTION_TEXT_RE.sub(" ", option.text.lower()).strip()
            in {"all of the above", "none of the above"}
            for option in item.options
        )
    ]
    checks.append(
        Check(
            "trivial_options",
            not trivial,
            f"{len(trivial)} MCQs contain all/none-of-the-above options",
            value=len(trivial),
        )
    )

    negative = [
        item.item_id
        for item in mcq_items
        if re.search(r"\bwhich\b.*\b(not|except)\b", item.prompt, re.IGNORECASE)
    ]
    checks.append(
        Check(
            "negative_stems",
            not negative,
            f"{len(negative)} MCQs use a negative equal-completion stem",
            value=len(negative),
        )
    )

    positions = validation.coverage.answer_positions
    max_position = max(positions.values(), default=0)
    max_share = max_position / len(mcq_items) if mcq_items else 0.0
    checks.append(
        Check(
            "answer_positions",
            max_share <= ANSWER_POSITION_CAP,
            f"max stored position holds {max_position}/{len(mcq_items)}",
            gated=len(mcq_items) >= 5,
            value=max_share,
            threshold=ANSWER_POSITION_CAP,
        )
    )

    bias, mean_gap, _ = _option_length_stats(mcq_items)
    checks.append(
        Check(
            "option_length_bias",
            bias <= 0.90,
            f"correct option is strictly longest in {bias:.2%} of MCQs; "
            f"mean gap {mean_gap:.2f}; cap 90%",
            value=bias,
            threshold=0.90,
        )
    )

    valid_short = 0
    for item in short_items:
        criterion_ids = {criterion.criterion_id for criterion in item.rubric}
        if (
            item.model_answer
            and 2 <= _sentences(item.model_answer) <= 3
            and 25 <= len(item.model_answer.split()) <= 80
            and {"correctness", "completeness"} <= criterion_ids
            and sum(criterion.max_marks for criterion in item.rubric) == item.marks
            and 2 <= len(item.required_points) <= 3
        ):
            valid_short += 1
    unsupported = [
        error for error in validation.errors if "required point is not supported" in error
    ]
    checks.append(
        Check(
            "short_quality",
            valid_short == len(short_items) and not unsupported,
            f"{valid_short}/{len(short_items)} short answers have valid length, "
            f"rubric and points; {len(unsupported)} unsupported points",
            value=valid_short,
            threshold=len(short_items),
        )
    )

    normalised = [normalise_prompt(item.prompt) for item in items]
    exact_duplicates = len(normalised) - len(set(normalised))
    max_jaccard, jaccard_pair = _max_jaccard(items)
    max_cosine: float | None = None
    cosine_pair: tuple[str, str] | None = None
    if embedder is not None:
        max_cosine, cosine_pair = await _max_cosine(items, embedder)
    duplicates_ok = (
        exact_duplicates == 0
        and max_jaccard < JACCARD_THRESHOLD
        and (max_cosine is None or max_cosine < COSINE_THRESHOLD)
    )
    checks.append(
        Check(
            "near_duplicates",
            duplicates_ok,
            f"exact={exact_duplicates} max_jaccard={max_jaccard:.4f} "
            f"(limit {JACCARD_THRESHOLD:.2f}) max_cosine="
            f"{max_cosine if max_cosine is None else f'{max_cosine:.4f}'} "
            f"(limit {COSINE_THRESHOLD:.2f})",
            value=max(max_jaccard, max_cosine or 0.0),
            threshold=COSINE_THRESHOLD,
        )
    )
    metrics.update(
        {
            "exact_duplicates": exact_duplicates,
            "max_jaccard": max_jaccard,
            "max_jaccard_pair": jaccard_pair,
            "max_cosine": max_cosine,
            "max_cosine_pair": cosine_pair,
            "embedder": getattr(embedder, "name", None) if embedder else None,
            "option_length_bias": bias,
            "option_length_mean_gap": mean_gap,
            "answer_positions": positions,
            "topic_counts": validation.coverage.per_topic_kind,
            "concept_counts": validation.coverage.per_concept_kind,
            "difficulty_counts": validation.coverage.difficulty,
        }
    )

    topic_failures: list[str] = []
    for topic, target in target_topics.items():
        topic_counts = validation.coverage.per_topic_kind.get(topic, {})
        mcq = topic_counts.get("mcq", 0)
        short = topic_counts.get("short_answer", 0)
        if abs(mcq - target) > 1 or abs(short - target) > 1:
            topic_failures.append(f"{topic}: mcq={mcq} short={short} target={target}")
    concept_failures = [
        f"{concept}: {kind_counts}"
        for concept, kind_counts in sorted(validation.coverage.per_concept_kind.items())
        if any(count > 2 for count in kind_counts.values())
    ]
    material_counts = {
        material.material_id: {"mcq": 0, "short_answer": 0}
        for material in pack.materials
    }
    for item in items:
        if item.material_id in material_counts:
            material_counts[item.material_id][item.kind] += 1
    material_failures = (
        [
            f"{material_id}: {kind_counts}"
            for material_id, kind_counts in sorted(material_counts.items())
            if kind_counts["mcq"] != 1 or kind_counts["short_answer"] != 1
        ]
        if material_targets
        else []
    )
    difficulty_failures: list[str] = []
    for kind in ("mcq", "short_answer"):
        totals = {
            group: sum(
                validation.coverage.difficulty.get(difficulty, {}).get(kind, 0)
                for difficulty in (
                    ["recall"]
                    if group == "recall"
                    else ["explanation", "application"]
                    if group == "explain_application"
                    else ["comparison", "scenario"]
                )
            )
            for group in target_difficulty
        }
        for group, target in target_difficulty.items():
            if abs(totals[group] - target) > 1:
                difficulty_failures.append(
                    f"{kind}/{group}: {totals[group]} target={target}"
                )
    coverage_ok = not (
        topic_failures or concept_failures or material_failures or difficulty_failures
    )
    checks.append(
        Check(
            "coverage",
            coverage_ok,
            f"topics={len(topic_failures)} concepts={len(concept_failures)} "
            f"materials={len(material_failures)} difficulty={len(difficulty_failures)}",
        )
    )
    metrics.update(
        {
            "topic_failures": topic_failures,
            "concept_failures": concept_failures,
            "material_counts": material_counts,
            "material_failures": material_failures,
            "difficulty_failures": difficulty_failures,
        }
    )
    return BankCheckReport(checks=checks, metrics=metrics)
