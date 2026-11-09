"""Exam attempt sampling, store round-trip and attempt-limit tests (#193)."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from app.api.limits import ExamAttemptLimiter
from app.config import Settings
from app.exam.attempts import sample_attempt
from app.exam.bank import ExamBank
from app.storage.exam_store import ExamStore
from eval.exam.fixtures import build_bank


def _bank_6_4() -> ExamBank:
    bank, _, _, _ = build_bank()
    mcq = bank.items[0]
    short = bank.items[1]
    mcqs = [
        mcq.model_copy(
            update={"item_id": f"dada-mcq-{index:03d}", "prompt": f"Sample MCQ {index}?"}
        )
        for index in range(1, 7)
    ]
    shorts = [
        short.model_copy(
            update={
                "item_id": f"dada-short-{index:03d}",
                "prompt": f"Sample short answer {index}?",
            }
        )
        for index in range(1, 5)
    ]
    manifest = bank.manifest.model_copy(
        update={"mcq_count": 6, "short_answer_count": 4}
    )
    return ExamBank(manifest=manifest, items=[*mcqs, *shorts])


def _record(bank: ExamBank, *, session_id: str = "session-a"):
    return sample_attempt(
        bank,
        attempt_id="attempt-1",
        paper_id="dada-1.0.0",
        created_at="2026-11-09T00:00:00Z",
        session_id=session_id,
        rng=random.Random(42),
    )


def test_sample_attempt_serves_four_options_without_the_key() -> None:
    bank = _bank_6_4()
    record = _record(bank)
    assert record.session_id == "session-a"
    assert len(record.questions) == 10
    mcqs = [question for question in record.questions if question.kind == "mcq"]
    shorts = [question for question in record.questions if question.kind == "short_answer"]
    assert len(mcqs) == 6
    assert len(shorts) == 4
    for question in mcqs:
        assert len(question.options) == 4
        assert len({option.option_id for option in question.options}) == 4
        assert question.correct_option_id in {
            option.option_id for option in question.options
        }
    view = record.view()
    assert view.marks == 50
    assert len(view.questions) == 10
    for question in view.questions:
        if question.kind == "mcq":
            assert len(question.options) == 4
            assert "correct_option_id" not in question.model_dump()
    assert "correct_option_id" not in view.model_dump_json()
    assert all(question.marks in (3, 8) for question in record.questions)


def test_store_round_trips_an_attempt(tmp_path) -> None:
    bank = _bank_6_4()
    store = ExamStore(tmp_path / "exams.db")
    try:
        store.replace_bank(bank)
        assert store.bank("dada") is not None
        record = _record(bank)
        store.create_attempt(record)
        loaded = store.attempt(record.attempt_id)
        assert loaded == record
        assert loaded is not None
        assert loaded.session_id == "session-a"
        assert loaded.view() == record.view()
    finally:
        store.close()


def test_list_attempts_is_session_scoped_and_graded_only(tmp_path) -> None:
    bank = _bank_6_4()
    store = ExamStore(tmp_path / "exams.db")
    try:
        store.replace_bank(bank)
        store.create_attempt(_record(bank, session_id="session-a"))
        assert store.list_attempts("session-a") == []
        assert store.list_attempts("session-b") == []
    finally:
        store.close()


def test_published_manifest_skips_a_newer_draft(tmp_path) -> None:
    bank = _bank_6_4()
    store = ExamStore(tmp_path / "exams.db")
    try:
        store.replace_bank(bank)
        draft_manifest = bank.manifest.model_copy(
            update={"version": "1.1.0", "status": "draft"}
        )
        store.replace_bank(ExamBank(manifest=draft_manifest, items=bank.items))
        published = store.published_manifest("dada")
        assert published is not None
        assert published.version == "1.0.0"
        assert store.published_manifest("dada", "1.1.0") is None
        assert store.bank("dada").manifest.version == "1.0.0"
    finally:
        store.close()


def test_exam_attempt_limiter_anonymous_and_signed_in() -> None:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    limiter = ExamAttemptLimiter(Settings(), now_utc=lambda: now)
    for _ in range(3):
        assert limiter.admit("anonymous").allowed
    limited = limiter.admit("anonymous")
    assert not limited.allowed
    assert limited.status == "rate_limited"
    for _ in range(5):
        assert limiter.admit("signed-in", signed_in=True).allowed
    assert not limiter.admit("signed-in", signed_in=True).allowed


def test_exam_attempt_limiter_ip_cap() -> None:
    now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    limiter = ExamAttemptLimiter(
        Settings(exam_attempts_per_day_ip=2), now_utc=lambda: now
    )
    assert limiter.admit("first", client_ip="203.0.113.7").allowed
    assert limiter.admit("second", client_ip="203.0.113.7").allowed
    limited = limiter.admit("third", client_ip="203.0.113.7")
    assert not limited.allowed
    assert limited.reason == "exam_ip_day"
    assert limiter.admit("fourth", client_ip="203.0.113.8").allowed
