"""Metrics for the lesson and multi-turn RAG fixtures.

These are deterministic where possible: selection, scope, citation and route
checks. Faithfulness is the one judged metric, and it is reported separately so
a judge failure cannot hide behind a retrieval number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.generate.lesson import LESSON_WORD_LIMIT
from app.schemas import Chunk
from eval.rag.fixtures import Conversation, LessonItem, Turn


@dataclass(frozen=True)
class LessonResult:
    """One lesson answer and the checks it passed."""

    item: LessonItem
    selected_material_ids: tuple[str, ...]
    material_citations: tuple[str, ...]
    citations: tuple[str, ...]
    book_citations: tuple[str, ...]
    scope: str | None
    abstained: bool
    answer: str
    citation_ok: bool
    source_hash_ok: bool
    chunks: tuple[Chunk, ...] = ()
    faithful: bool | None = None
    error: str | None = None

    @property
    def selection_precision(self) -> float:
        if not self.item.answerable:
            return 0.0
        selected = set(self.selected_material_ids[:3])
        expected = set(self.item.expected_material_ids)
        return len(selected & expected) / len(selected) if selected else 0.0

    @property
    def selection_recall(self) -> float:
        if not self.item.answerable:
            return 0.0
        selected = set(self.selected_material_ids[:3])
        expected = set(self.item.expected_material_ids)
        return len(selected & expected) / len(expected) if expected else 0.0

    @property
    def citation_recall(self) -> float:
        if not self.item.answerable:
            return 0.0
        parts: list[float] = []
        cited = set(self.material_citations)
        if self.item.expected_groups:
            hits = sum(1 for group in self.item.expected_groups if cited & set(group.material_ids))
            parts.append(hits / len(self.item.expected_groups))
        elif self.item.expected_material_ids:
            expected = set(self.item.expected_material_ids)
            parts.append(len(cited & expected) / len(expected))
        if self.item.expected_chunk_ids:
            cited_chunks = set(self.book_citations)
            expected_chunks = set(self.item.expected_chunk_ids)
            # The expected chunks are alternatives, not a required set: any
            # valid evidence chunk is a hit. The material group check above is
            # the required part.
            parts.append(1.0 if cited_chunks & expected_chunks else 0.0)
        return sum(parts) / len(parts) if parts else 0.0

    @property
    def scope_ok(self) -> bool:
        return self.scope == self.item.expected_scope

    @property
    def false_refusal(self) -> bool:
        return self.item.answerable and self.abstained

    @property
    def abstention_ok(self) -> bool:
        return not self.item.answerable and self.abstained


@dataclass(frozen=True)
class LessonMetrics:
    """Aggregate lesson metrics."""

    total: int
    answerable: int
    unanswerable: int
    selection_precision_at_3: float
    selection_recall_at_3: float
    scope_accuracy: float
    citation_recall: float
    false_refusal_rate: float
    abstention_accuracy: float
    citation_validity_rate: float
    source_hash_rate: float
    mixed_count: int
    mixed_scope_accuracy: float
    mixed_citation_recall: float
    mixed_false_refusal_rate: float
    off_pack_count: int
    off_pack_scope_accuracy: float
    off_pack_citation_recall: float
    off_pack_false_refusal_rate: float
    mean_words: float
    max_words: int
    length_violations: int
    judged: int
    faithfulness_rate: float
    errors: int


def summarize_lesson(results: list[LessonResult]) -> LessonMetrics:
    """Aggregate one lesson run."""
    answerable = [result for result in results if result.item.answerable]
    unanswerable = [result for result in results if not result.item.answerable]
    selection_items = [result for result in answerable if result.item.expected_material_ids]
    mixed = [result for result in results if result.item.slice_name == "mixed"]
    off_pack = [result for result in results if result.item.slice_name == "off_pack"]
    judged = [result for result in results if result.faithful is not None]
    answered = [
        result
        for result in results
        if not result.abstained and result.answer.strip()
    ]
    # Citation tokens and the deterministic mixed/off-pack label are counted:
    # this is prompt weight, not prose length.
    word_counts = [
        len(re.findall(r"[A-Za-z0-9]+", result.answer)) for result in answered
    ]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def false_refusal(items: list[LessonResult]) -> float:
        return mean([float(result.false_refusal) for result in items])

    return LessonMetrics(
        total=len(results),
        answerable=len(answerable),
        unanswerable=len(unanswerable),
        selection_precision_at_3=mean([result.selection_precision for result in selection_items]),
        selection_recall_at_3=mean([result.selection_recall for result in selection_items]),
        scope_accuracy=mean([float(result.scope_ok) for result in results]),
        citation_recall=mean([result.citation_recall for result in answerable]),
        false_refusal_rate=mean([float(result.false_refusal) for result in answerable]),
        abstention_accuracy=mean([float(result.abstention_ok) for result in unanswerable]),
        citation_validity_rate=mean([float(result.citation_ok) for result in results]),
        source_hash_rate=mean([float(result.source_hash_ok) for result in results]),
        mixed_count=len(mixed),
        mixed_scope_accuracy=mean([float(result.scope_ok) for result in mixed]),
        mixed_citation_recall=mean([result.citation_recall for result in mixed]),
        mixed_false_refusal_rate=false_refusal(mixed),
        off_pack_count=len(off_pack),
        off_pack_scope_accuracy=mean([float(result.scope_ok) for result in off_pack]),
        off_pack_citation_recall=mean([result.citation_recall for result in off_pack]),
        off_pack_false_refusal_rate=false_refusal(off_pack),
        mean_words=mean([float(count) for count in word_counts]),
        max_words=max(word_counts) if word_counts else 0,
        length_violations=sum(
            1 for count in word_counts if count >= LESSON_WORD_LIMIT
        ),
        judged=len(judged),
        faithfulness_rate=mean([float(result.faithful is True) for result in judged]),
        errors=sum(1 for result in results if result.error is not None),
    )


@dataclass(frozen=True)
class TurnResult:
    """One multi-turn turn and its expected/actual values."""

    conversation: Conversation
    turn: Turn
    turn_index: int
    actual_standalone: str
    actual_mode: str
    actual_material_ids: tuple[str, ...]
    actual_abstained: bool
    actual_referral_subject: str | None
    actual_referral_concept: str | None
    answer: str
    error: str | None = None

    @property
    def query_ok(self) -> bool:
        return (
            " ".join(self.actual_standalone.split()).casefold()
            == " ".join(self.turn.expected_standalone.split()).casefold()
        )

    @property
    def mode_ok(self) -> bool:
        return self.actual_mode == self.turn.expected_mode

    @property
    def citation_ok(self) -> bool:
        actual = set(self.actual_material_ids)
        if self.turn.expected_groups:
            return all(actual & set(group.material_ids) for group in self.turn.expected_groups)
        expected = set(self.turn.expected_material_ids)
        return expected.issubset(actual)

    @property
    def abstention_ok(self) -> bool:
        if self.turn.expected_abstained is None:
            return True
        return self.actual_abstained == self.turn.expected_abstained

    @property
    def referral_ok(self) -> bool:
        if self.turn.expected_referral_subject is None:
            return True
        return (
            self.actual_referral_subject == self.turn.expected_referral_subject
            and self.actual_referral_concept == self.turn.expected_referral_concept
        )


@dataclass(frozen=True)
class MultiTurnMetrics:
    """Aggregate multi-turn metrics."""

    conversations: int
    turns: int
    query_accuracy: float
    mode_accuracy: float
    citation_accuracy: float
    false_refusal_rate: float
    abstention_accuracy: float
    referral_target_accuracy: float
    comparison_accuracy: float
    context_contamination: int
    errors: int


def summarize_multiturn(results: list[TurnResult]) -> MultiTurnMetrics:
    """Aggregate one multi-turn run.

    False refusal and abstention are separate denominators: a turn that should
    answer must not abstain, and a turn that should abstain must not answer.
    Comparison accuracy is measured only on turns with two expected concept
    groups, not on every turn in a comparison conversation.
    """
    compared = [result for result in results if len(result.turn.expected_groups) >= 2]
    referral = [result for result in results if result.turn.expected_referral_subject]
    should_answer = [result for result in results if result.turn.expected_abstained is False]
    should_abstain = [result for result in results if result.turn.expected_abstained is True]
    cited = [result for result in results if result.turn.expected_material_ids]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return MultiTurnMetrics(
        conversations=len({result.conversation.conversation_id for result in results}),
        turns=len(results),
        query_accuracy=mean([float(result.query_ok) for result in results]),
        mode_accuracy=mean([float(result.mode_ok) for result in results]),
        citation_accuracy=mean([float(result.citation_ok) for result in cited]),
        false_refusal_rate=mean([float(result.actual_abstained) for result in should_answer]),
        abstention_accuracy=mean([float(result.actual_abstained) for result in should_abstain]),
        referral_target_accuracy=mean([float(result.referral_ok) for result in referral]),
        comparison_accuracy=mean(
            [float(result.mode_ok and result.citation_ok) for result in compared]
        ),
        context_contamination=sum(
            1
            for result in results
            if result.conversation.slice_name == "off_topic"
            and result.turn.expected_abstained is True
            and not result.actual_abstained
        ),
        errors=sum(1 for result in results if result.error is not None),
    )


@dataclass(frozen=True)
class RagReport:
    """One lesson + multi-turn run."""

    run_id: str
    config: str
    generator: str
    judge: str
    lesson_sample: int
    lesson_fixture_sha: str
    multiturn_fixture_sha: str
    settings: dict[str, object]
    lesson: LessonMetrics
    multiturn: MultiTurnMetrics

    @property
    def errors(self) -> int:
        return self.lesson.errors + self.multiturn.errors

    @property
    def ok(self) -> bool:
        return self.errors == 0


__all__ = [
    "LessonMetrics",
    "LessonResult",
    "MultiTurnMetrics",
    "RagReport",
    "TurnResult",
    "summarize_lesson",
    "summarize_multiturn",
]
