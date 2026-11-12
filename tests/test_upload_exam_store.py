"""The exam-store upload script refuses unsafe or incomplete banks (#255)."""

from __future__ import annotations

import re
import sqlite3
import sys
import tarfile
from types import SimpleNamespace

import pytest

import scripts.backup_lexicon as backup
from app.storage.exam_store import ExamStore
from eval.exam.fixtures import build_bank
from scripts.upload_exam_store import (
    UploadError,
    main,
    presign,
    snapshot,
    upload,
    validate_snapshot,
)


def _store(tmp_path):
    bank, *_ = build_bank()
    store = ExamStore(tmp_path / "exams.db")
    store.replace_bank(bank)
    store.close()
    return tmp_path / "exams.db"


def test_snapshot_copies_a_complete_bank(tmp_path):
    source = _store(tmp_path)
    dest = tmp_path / "snapshot.db"
    snapshot(source, dest)
    stats = validate_snapshot(dest, min_banks=1)
    assert stats.banks == 1
    assert stats.items == 2
    assert stats.attempts == 0
    assert stats.subjects == ("dada",)


def test_validate_counts_servable_subjects_not_bank_rows(tmp_path):
    bank, *_ = build_bank()
    source = tmp_path / "exams.db"
    store = ExamStore(source)
    store.replace_bank(bank)
    latest = bank.model_copy(
        update={"manifest": bank.manifest.model_copy(update={"version": "1.1.0"})}
    )
    store.replace_bank(latest)
    draft = bank.model_copy(
        update={
            "manifest": bank.manifest.model_copy(
                update={"version": "1.2.0", "status": "draft"}
            )
        }
    )
    store.replace_bank(draft)
    store.close()

    stats = validate_snapshot(source, min_banks=1)
    assert stats.banks == 1
    assert stats.subjects == ("dada",)
    assert stats.items == 2
    with pytest.raises(UploadError, match="servable subjects"):
        validate_snapshot(source, min_banks=2)


def test_validate_refuses_attempt_history_by_default(tmp_path):
    source = _store(tmp_path)
    with sqlite3.connect(source) as conn:
        conn.execute(
            "INSERT INTO attempts "
            "(attempt_id, paper_id, subject, bank_version, created_at) "
            "VALUES ('a', 'dada-1.0.0', 'dada', '1.0.0', '2026-11-12T00:00:00Z')"
        )
    with pytest.raises(UploadError, match="attempts"):
        validate_snapshot(source, min_banks=1)
    stats = validate_snapshot(source, min_banks=1, allow_attempts=True)
    assert stats.attempts == 1


def test_validate_refuses_missing_item_rows(tmp_path):
    source = _store(tmp_path)
    with sqlite3.connect(source) as conn:
        conn.execute("DELETE FROM bank_items WHERE kind = 'mcq'")
    with pytest.raises(UploadError, match="declares 2 items but stores 1"):
        validate_snapshot(source, min_banks=1)


def test_validate_refuses_too_few_banks(tmp_path):
    source = _store(tmp_path)
    with pytest.raises(UploadError, match="servable subjects"):
        validate_snapshot(source, min_banks=2)


def test_upload_writes_a_timestamped_key_and_alias(tmp_path, monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="")

    monkeypatch.setattr("scripts.upload_exam_store.subprocess.run", fake_run)
    source = tmp_path / "exams.db"
    source.write_bytes(b"snapshot")
    key, alias = upload(source, bucket="bucket", region="region", prefix="deploy")
    assert re.fullmatch(r"deploy/owl-exams-\d{8}T\d{12}Z\.db", key)
    assert alias == "deploy/owl-exams.db"

    copy_args, copy_kwargs = calls[0]
    assert copy_args[:3] == ["aws", "s3", "cp"]
    assert copy_args[-1] == f"s3://bucket/{key}"
    assert copy_kwargs["check"] is True
    assert "shell" not in copy_kwargs

    alias_args, alias_kwargs = calls[1]
    assert alias_args[:3] == ["aws", "s3api", "copy-object"]
    assert alias_args[alias_args.index("--copy-source") + 1] == f"bucket/{key}"
    assert alias_args[alias_args.index("--key") + 1] == alias
    assert alias_kwargs["check"] is True
    assert "shell" not in alias_kwargs


def test_presign_returns_the_cli_url(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="https://example.test/signed\n")

    monkeypatch.setattr("scripts.upload_exam_store.subprocess.run", fake_run)
    url = presign(
        bucket="bucket",
        region="region",
        key="deploy/owl-exams.db",
        expires_in=300,
    )
    assert url == "https://example.test/signed"
    args, kwargs = calls[0]
    assert args[:3] == ["aws", "s3", "presign"]
    assert args[args.index("--expires-in") + 1] == "300"
    assert args[-1] == "s3://bucket/deploy/owl-exams.db"
    assert kwargs["check"] is True
    assert "shell" not in kwargs


def test_main_dry_run_does_not_upload(tmp_path, monkeypatch):
    source = _store(tmp_path)
    uploaded = []
    monkeypatch.setattr(
        "scripts.upload_exam_store.upload",
        lambda *a, **k: uploaded.append((a, k)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["upload", "--source", str(source), "--min-banks", "1", "--dry-run"],
    )
    assert main() == 0
    assert uploaded == []


def test_main_refuses_a_partial_store(tmp_path, monkeypatch, capsys):
    source = _store(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["upload", "--source", str(source), "--min-banks", "2"],
    )
    assert main() == 1
    assert "refusing upload" in capsys.readouterr().err


def test_main_rejects_presign_with_dry_run(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["upload", "--dry-run", "--presign"])
    with pytest.raises(SystemExit):
        main()


def test_data_bundle_snapshots_the_exam_store(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "index" / "chroma").mkdir(parents=True)
    (data / "index" / "chroma" / "keep").write_text("x")
    for member in ("chunks.jsonl", "chunks_context.jsonl", "rerank_cache.jsonl"):
        (data / member).write_text("{}")
    for member in ("lore", "subjects"):
        (data / member).mkdir()
        (data / member / "keep").write_text("x")

    bank, *_ = build_bank()
    store = ExamStore(data / "exams" / "exams.db")
    store.replace_bank(bank)
    store.close()

    snapshots = []
    real_snapshot = backup.snapshot

    def record_snapshot(source, dest):
        snapshots.append((source, dest))
        real_snapshot(source, dest)

    monkeypatch.setattr(backup, "snapshot", record_snapshot)
    monkeypatch.setattr(backup, "DATA", data)
    staging = tmp_path / "stage"
    staging.mkdir()
    bundle = backup.build_tar("data", staging)

    assert snapshots == [
        (data / "exams" / "exams.db", staging / "data" / "exams" / "exams.db")
    ]
    with tarfile.open(bundle) as archive:
        names = archive.getnames()
        assert "data/exams/exams.db" in names
        for member in (
            "data/subjects/keep",
            "data/lore/keep",
            "data/index/chroma/keep",
        ):
            entry = archive.getmember(member)
            assert entry.isreg(), member
            assert archive.extractfile(entry).read() == b"x"
        member = archive.extractfile("data/exams/exams.db")
        assert member is not None
        restored = tmp_path / "restored.db"
        restored.write_bytes(member.read())
    stats = validate_snapshot(restored, min_banks=1)
    assert stats.banks == 1
    assert stats.items == 2
