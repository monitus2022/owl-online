"""Metric and gate tests; no network, no model calls."""

from __future__ import annotations

import json
from pathlib import Path

from eval.rag.check import check_rag
from eval.rag.fixtures import Conversation, GroupExpectation, LessonItem, Turn
from eval.rag.metrics import (
    LessonResult,
    TurnResult,
    summarize_lesson,
    summarize_multiturn,
)


def _lesson_item(*, item_id: str = "l1", answerable: bool = True) -> LessonItem:
    return LessonItem(
        item_id=item_id,
        subject="dada",
        question="Tell me about Boggart.",
        slice_name="in_pack" if answerable else "abstain",
        answerable=answerable,
        expected_scope="in_pack" if answerable else "abstained",
        citation="material" if answerable else "none",
        expected_material_ids=("a", "b") if answerable else (),
        expected_source_refs=(),
    )


def _lesson_result(
    *,
    item: LessonItem,
    selected: tuple[str, ...] = ("a", "x"),
    cited: tuple[str, ...] = ("a",),
    book_citations: tuple[str, ...] | None = None,
    scope: str | None = "in_pack",
    abstained: bool = False,
    faithful: bool | None = True,
) -> LessonResult:
    return LessonResult(
        item=item,
        selected_material_ids=selected,
        material_citations=cited,
        citations=cited,
        book_citations=cited if book_citations is None else book_citations,
        scope=scope,
        abstained=abstained,
        answer="answer",
        citation_ok=True,
        source_hash_ok=True,
        faithful=faithful,
    )


def test_lesson_result_scores_selection_and_citations():
    result = _lesson_result(item=_lesson_item())
    assert result.selection_precision == 0.5
    assert result.selection_recall == 0.5
    assert result.citation_recall == 0.5
    assert result.scope_ok is True
    assert result.false_refusal is False


def test_lesson_result_flags_false_refusal_and_abstention():
    refused = _lesson_result(item=_lesson_item(), abstained=True)
    assert refused.false_refusal is True
    unanswerable = _lesson_result(
        item=_lesson_item(item_id="l2", answerable=False),
        selected=(),
        cited=(),
        scope="abstained",
        abstained=True,
        faithful=None,
    )
    assert unanswerable.abstention_ok is True
    assert unanswerable.false_refusal is False


def test_lesson_citation_recall_is_one_per_expected_group():
    item = LessonItem(
        item_id="l-grouped",
        subject="dada",
        question="Compare A with B.",
        slice_name="multi_concept",
        answerable=True,
        expected_scope="in_pack",
        citation="material",
        expected_material_ids=("a1", "a2", "b1"),
        expected_source_refs=(),
        expected_groups=(
            GroupExpectation("A", ("a1", "a2")),
            GroupExpectation("B", ("b1",)),
        ),
    )
    partial = _lesson_result(item=item, selected=("a1", "a2", "b1"), cited=("a2",))
    assert partial.citation_recall == 0.5
    complete = _lesson_result(item=item, selected=("a1", "a2", "b1"), cited=("a2", "b1"))
    assert complete.citation_recall == 1.0


def test_lesson_citation_recall_uses_explicit_book_citations():
    item = LessonItem(
        item_id="l-off-pack",
        subject="dada",
        question="What is the name of the three-headed dog?",
        slice_name="off_pack",
        answerable=True,
        expected_scope="off_pack",
        citation="book",
        expected_material_ids=(),
        expected_source_refs=(),
        expected_chunk_ids=("b1-c11-0042",),
    )
    partial = _lesson_result(
        item=item,
        selected=(),
        cited=(),
        book_citations=("b1-c15-0018",),
    )
    assert partial.citation_recall == 0.0
    complete = _lesson_result(
        item=item,
        selected=(),
        cited=(),
        book_citations=("b1-c11-0042",),
    )
    assert complete.citation_recall == 1.0


def test_summarize_lesson_reports_false_refusal_and_abstention():
    metrics = summarize_lesson(
        [
            _lesson_result(item=_lesson_item()),
            _lesson_result(
                item=_lesson_item(item_id="l2", answerable=False),
                selected=(),
                cited=(),
                scope="abstained",
                abstained=True,
                faithful=None,
            ),
        ]
    )
    assert metrics.total == 2
    assert metrics.answerable == 1
    assert metrics.unanswerable == 1
    assert metrics.false_refusal_rate == 0.0
    assert metrics.abstention_accuracy == 1.0
    assert metrics.faithfulness_rate == 1.0


def _turn() -> Turn:
    return Turn(
        question="what about Dementors?",
        mode="lesson",
        expected_standalone="Compare Boggart with Dementors.",
        expected_mode="lesson",
        expected_material_ids=("b", "d"),
    )


def _conversation() -> Conversation:
    return Conversation(
        conversation_id="c1",
        subject="dada",
        slice_name="same_subject_comparison",
        turns=(_turn(),),
    )


def test_turn_result_checks_query_mode_citation_and_abstention():
    result = TurnResult(
        conversation=_conversation(),
        turn=_turn(),
        turn_index=1,
        actual_standalone="Compare Boggart with Dementors.",
        actual_mode="lesson",
        actual_material_ids=("b", "d"),
        actual_abstained=False,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="answer",
    )
    assert result.query_ok is True
    assert result.mode_ok is True
    assert result.citation_ok is True
    assert result.abstention_ok is True
    assert result.referral_ok is True


def test_turn_citation_is_one_per_expected_group():
    turn = Turn(
        question="what about Dementors?",
        mode="lesson",
        expected_standalone="Compare Boggart with Dementors.",
        expected_mode="lesson",
        expected_material_ids=("b1", "b2", "d1"),
        expected_groups=(
            GroupExpectation("Boggart", ("b1", "b2")),
            GroupExpectation("Dementors", ("d1",)),
        ),
    )
    conversation = Conversation(
        conversation_id="c-grouped",
        subject="dada",
        slice_name="same_subject_comparison",
        turns=(turn,),
    )
    complete = TurnResult(
        conversation=conversation,
        turn=turn,
        turn_index=1,
        actual_standalone="Compare Boggart with Dementors.",
        actual_mode="lesson",
        actual_material_ids=("b2", "d1"),
        actual_abstained=False,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="answer",
    )
    assert complete.citation_ok is True
    partial = TurnResult(
        conversation=conversation,
        turn=turn,
        turn_index=1,
        actual_standalone="Compare Boggart with Dementors.",
        actual_mode="lesson",
        actual_material_ids=("b2",),
        actual_abstained=False,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="answer",
    )
    assert partial.citation_ok is False


def test_turn_result_flags_a_missing_citation_and_wrong_mode():
    result = TurnResult(
        conversation=_conversation(),
        turn=_turn(),
        turn_index=1,
        actual_standalone="Compare Boggart with Dementors.",
        actual_mode="abstain",
        actual_material_ids=("b",),
        actual_abstained=True,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="",
    )
    assert result.mode_ok is False
    assert result.citation_ok is False
    assert result.abstention_ok is False


def test_summarize_multiturn_counts_referral_and_contamination():
    turn = Turn(
        question="what about Avifors?",
        mode="lesson",
        expected_standalone="Compare Disarming Charm with Avifors.",
        expected_mode="referral",
        expected_material_ids=("disarming",),
        expected_abstained=False,
        expected_referral_subject="charms",
        expected_referral_concept="Avifors",
    )
    conversation = Conversation(
        conversation_id="c2",
        subject="dada",
        slice_name="cross_subject",
        turns=(turn,),
    )
    result = TurnResult(
        conversation=conversation,
        turn=turn,
        turn_index=1,
        actual_standalone="Compare Disarming Charm with Avifors.",
        actual_mode="referral",
        actual_material_ids=("disarming",),
        actual_abstained=False,
        actual_referral_subject="charms",
        actual_referral_concept="Avifors",
        answer="Avifors belongs to Charms.",
    )
    metrics = summarize_multiturn([result])
    assert metrics.referral_target_accuracy == 1.0
    assert metrics.context_contamination == 0


def test_comparison_accuracy_uses_only_two_group_turns():
    first_turn = Turn(
        question="Tell me about Boggart.",
        mode="lesson",
        expected_standalone="Tell me about Boggart.",
        expected_mode="lesson",
        expected_groups=(GroupExpectation("Boggart", ("b1",)),),
        expected_abstained=False,
    )
    second_turn = Turn(
        question="what about Dementors?",
        mode="lesson",
        expected_standalone="Compare Boggart with Dementors.",
        expected_mode="lesson",
        expected_groups=(
            GroupExpectation("Boggart", ("b1",)),
            GroupExpectation("Dementors", ("d1",)),
        ),
        expected_abstained=False,
    )
    conversation = Conversation(
        conversation_id="c-comparison",
        subject="dada",
        slice_name="same_subject_comparison",
        turns=(first_turn, second_turn),
    )
    first = TurnResult(
        conversation=conversation,
        turn=first_turn,
        turn_index=1,
        actual_standalone="Tell me about Boggart.",
        actual_mode="abstain",
        actual_material_ids=(),
        actual_abstained=True,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="",
    )
    second = TurnResult(
        conversation=conversation,
        turn=second_turn,
        turn_index=2,
        actual_standalone="Compare Boggart with Dementors.",
        actual_mode="lesson",
        actual_material_ids=("b1", "d1"),
        actual_abstained=False,
        actual_referral_subject=None,
        actual_referral_concept=None,
        answer="answer",
    )
    metrics = summarize_multiturn([first, second])
    assert metrics.comparison_accuracy == 1.0


def test_multiturn_false_refusal_and_abstention_use_separate_denominators():
    should_answer = Turn(
        question="Tell me about Boggart.",
        mode="lesson",
        expected_standalone="Tell me about Boggart.",
        expected_mode="lesson",
        expected_abstained=False,
    )
    should_abstain = Turn(
        question="What is the capital of France?",
        mode="lesson",
        expected_standalone="What is the capital of France?",
        expected_mode="abstain",
        expected_abstained=True,
    )
    conversation = Conversation(
        conversation_id="c-denominators",
        subject="dada",
        slice_name="off_topic",
        turns=(should_answer, should_abstain),
    )
    results = [
        TurnResult(
            conversation=conversation,
            turn=should_answer,
            turn_index=1,
            actual_standalone="Tell me about Boggart.",
            actual_mode="lesson",
            actual_material_ids=(),
            actual_abstained=True,
            actual_referral_subject=None,
            actual_referral_concept=None,
            answer="",
        ),
        TurnResult(
            conversation=conversation,
            turn=should_abstain,
            turn_index=2,
            actual_standalone="What is the capital of France?",
            actual_mode="abstain",
            actual_material_ids=(),
            actual_abstained=True,
            actual_referral_subject=None,
            actual_referral_concept=None,
            answer="",
        ),
    ]
    metrics = summarize_multiturn(results)
    assert metrics.false_refusal_rate == 1.0
    assert metrics.abstention_accuracy == 1.0


def _report_dict(
    *,
    faithfulness: float = 0.8,
    lesson_sha: str = "lesson-sha",
    mixed_citation: float = 1.0,
) -> dict[str, object]:
    return {
        "lesson_fixture_sha": lesson_sha,
        "multiturn_fixture_sha": "multiturn-sha",
        "lesson_sample": 30,
        "settings": {"generator_temperature": 0.0},
        "lesson": {
            "total": 60,
            "answerable": 50,
            "unanswerable": 10,
            "judged": 30,
            "selection_precision_at_3": 0.8,
            "selection_recall_at_3": 0.9,
            "scope_accuracy": 0.9,
            "citation_recall": 0.9,
            "false_refusal_rate": 0.1,
            "abstention_accuracy": 1.0,
            "citation_validity_rate": 1.0,
            "source_hash_rate": 1.0,
            "mixed_count": 1,
            "mixed_scope_accuracy": 1.0,
            "mixed_citation_recall": mixed_citation,
            "mixed_false_refusal_rate": 0.0,
            "off_pack_count": 1,
            "off_pack_scope_accuracy": 1.0,
            "off_pack_citation_recall": 1.0,
            "off_pack_false_refusal_rate": 0.0,
            "faithfulness_rate": faithfulness,
            "errors": 0,
        },
        "multiturn": {
            "conversations": 17,
            "turns": 36,
            "query_accuracy": 0.8,
            "mode_accuracy": 0.8,
            "citation_accuracy": 0.8,
            "false_refusal_rate": 0.0,
            "abstention_accuracy": 1.0,
            "referral_target_accuracy": 0.0,
            "comparison_accuracy": 0.8,
            "context_contamination": 0,
            "errors": 0,
        },
    }


def test_check_rag_passes_when_metrics_are_within_band(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    latest = tmp_path / "latest.json"
    baseline.write_text(json.dumps(_report_dict()), encoding="utf-8")
    latest.write_text(json.dumps(_report_dict(faithfulness=0.78)), encoding="utf-8")
    report = check_rag(baseline, latest)
    assert report.passed is True


def test_check_rag_fails_when_faithfulness_drops(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    latest = tmp_path / "latest.json"
    baseline.write_text(json.dumps(_report_dict()), encoding="utf-8")
    latest.write_text(json.dumps(_report_dict(faithfulness=0.5)), encoding="utf-8")
    report = check_rag(baseline, latest)
    assert report.passed is False
    assert any(failure.delta.name == "lesson_faithfulness_rate" for failure in report.failures)


def test_check_rag_fails_when_the_mixed_slice_drops(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    latest = tmp_path / "latest.json"
    baseline.write_text(json.dumps(_report_dict()), encoding="utf-8")
    latest.write_text(json.dumps(_report_dict(mixed_citation=0.0)), encoding="utf-8")
    report = check_rag(baseline, latest)
    assert report.passed is False
    assert any(failure.delta.name == "lesson_mixed_citation_recall" for failure in report.failures)


def test_check_rag_fails_when_the_settings_change(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    latest = tmp_path / "latest.json"
    baseline.write_text(json.dumps(_report_dict()), encoding="utf-8")
    payload = _report_dict()
    payload["settings"] = {"generator_temperature": 0.7}
    latest.write_text(json.dumps(payload), encoding="utf-8")
    report = check_rag(baseline, latest)
    assert report.passed is False
    assert report.fixture_mismatch == ("settings",)


def test_check_rag_fails_when_the_fixture_changes(tmp_path: Path):
    baseline = tmp_path / "baseline.json"
    latest = tmp_path / "latest.json"
    baseline.write_text(json.dumps(_report_dict()), encoding="utf-8")
    latest.write_text(json.dumps(_report_dict(lesson_sha="different")), encoding="utf-8")
    report = check_rag(baseline, latest)
    assert report.passed is False
    assert report.fixture_mismatch == ("lesson_fixture_sha",)
