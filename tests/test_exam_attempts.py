"""Exam attempt sampling, store round-trip and attempt-limit tests (#193)."""

from __future__ import annotations

import random
import sqlite3
from datetime import UTC, datetime

from app.api.limits import ExamAttemptLimiter
from app.config import Settings
from app.exam.attempts import sample_attempt
from app.exam.bank import ExamBank
from app.grading import band_for
from app.grading.models import AttemptGrade, CriterionGrade, QuestionGrade
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


def _record(
    bank: ExamBank, *, session_id: str = "session-a", attempt_id: str = "attempt-1"
):
    return sample_attempt(
        bank,
        attempt_id=attempt_id,
        paper_id="dada-1.0.0",
        created_at="2026-11-09T00:00:00Z",
        session_id=session_id,
        rng=random.Random(42),
    )


def _grade(record) -> AttemptGrade:
    questions: list[QuestionGrade] = []
    for question in record.questions:
        if question.kind == "mcq":
            questions.append(
                QuestionGrade(
                    item_id=question.item_id,
                    kind="mcq",
                    marks_awarded=question.marks,
                    max_marks=question.marks,
                    correct=True,
                    correct_option_id=question.correct_option_id,
                    model_answer="Correct option",
                    feedback="Correct.",
                    material_id="material-1",
                    evidence_ids=("chunk-1",),
                    rubric_version="v1",
                )
            )
        else:
            criteria = (
                CriterionGrade(
                    criterion_id="correctness",
                    awarded=4,
                    max_marks=4,
                    reason="Correct.",
                ),
                CriterionGrade(
                    criterion_id="completeness",
                    awarded=4,
                    max_marks=4,
                    reason="Complete.",
                ),
            )
            questions.append(
                QuestionGrade(
                    item_id=question.item_id,
                    kind="short_answer",
                    marks_awarded=8,
                    max_marks=8,
                    model_answer="Model answer",
                    criteria=criteria,
                    feedback="Complete.",
                    material_id="material-1",
                    evidence_ids=("chunk-1",),
                    rubric_version="v1",
                )
            )
    total = sum(question.marks_awarded or 0 for question in questions)
    max_marks = sum(question.max_marks for question in questions)
    return AttemptGrade(
        bank_version=record.bank_version,
        subject=record.subject,
        judge_model="mistralai/mistral-small-3.2-24b-instruct",
        judge_temperature=0.0,
        judge_provider="openrouter",
        judge_max_tokens=2000,
        judge_prompt_version="dada-bank-judge-v2",
        graded_at="2026-11-10T00:00:00Z",
        questions=tuple(questions),
        total=total,
        max_marks=max_marks,
        band=band_for(total, max_marks),
        needs_review=False,
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


def test_list_attempts_returns_graded_rows_for_the_session(tmp_path) -> None:
    bank = _bank_6_4()
    store = ExamStore(tmp_path / "exams.db")
    try:
        store.replace_bank(bank)
        first = _record(bank, session_id="session-a", attempt_id="attempt-1")
        second = _record(bank, session_id="session-a", attempt_id="attempt-2")
        other = _record(bank, session_id="session-b", attempt_id="attempt-3")
        for record in (first, second, other):
            store.create_attempt(record)
            store.save_grade(record.attempt_id, _grade(record))
        listed = store.list_attempts("session-a")
        assert [row.attempt_id for row in listed] == ["attempt-2", "attempt-1"]
        assert all(row.total == 50 and row.max_marks == 50 for row in listed)
        assert all(row.band == "O" for row in listed)
        assert store.list_attempts("session-b")[0].attempt_id == "attempt-3"
        assert store.list_attempts("session-a", limit=1)[0].attempt_id == "attempt-2"
        assert store.list_attempts("session-a", subject="potions") == []
    finally:
        store.close()


def test_migration_adds_session_ownership_to_an_old_store(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE attempts (
                attempt_id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                bank_version TEXT NOT NULL,
                created_at TEXT NOT NULL,
                graded_at TEXT,
                grade_json TEXT
            );
            INSERT INTO attempts
                (attempt_id, paper_id, subject, bank_version, created_at)
            VALUES
                ('legacy', 'dada-1.0.0', 'dada', '1.0.0', '2026-11-09T00:00:00Z');
            """
        )
    store = ExamStore(path)
    try:
        with sqlite3.connect(path) as conn:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(attempts)")
            }
            indexes = {
                row[1] for row in conn.execute("PRAGMA index_list(attempts)")
            }
        assert "session_id" in columns
        assert "answers_json" in columns
        assert "attempts_session" in indexes
        with sqlite3.connect(path) as conn:
            row = conn.execute(
                "SELECT session_id FROM attempts WHERE attempt_id = 'legacy'"
            ).fetchone()
        assert row is not None
        assert row[0] == ""
        assert store.list_attempts("session-a") == []
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
