"""Deterministic bank-check tests, no network."""

from __future__ import annotations

from pathlib import Path

from app.providers.contracts import Embedder
from eval.exam.calibration import load_calibration
from eval.exam.checks import run_deterministic_checks
from eval.exam.fixtures import build_bank


class _Embedder(Embedder):
    name = "fake/embedder"

    async def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


async def test_small_bank_passes_deterministic_checks() -> None:
    bank, pack, chunks, index_hash = build_bank()
    report = await run_deterministic_checks(
        bank,
        pack,
        chunks,
        index_hash,
        target_counts=(1, 1),
        topic_targets={},
        difficulty_targets={},
    )
    assert report.ok, [check.name for check in report.failures]
    checks = {check.name: check for check in report.checks}
    assert checks["counts"].ok
    assert checks["coverage"].ok
    assert checks["near_duplicates"].ok
    assert checks["option_length_bias"].gated is False


async def test_duplicate_prompt_fails_the_checks() -> None:
    bank, pack, chunks, index_hash = build_bank()
    bank.items.append(bank.items[0].model_copy(update={"item_id": "dada-mcq-002"}))
    report = await run_deterministic_checks(
        bank,
        pack,
        chunks,
        index_hash,
        target_counts=(1, 1),
        topic_targets={},
        difficulty_targets={},
    )
    checks = {check.name: check for check in report.checks}
    assert not report.ok
    assert not checks["near_duplicates"].ok
    assert not checks["bank_validation"].ok


async def test_embedding_cosine_flags_a_duplicate() -> None:
    bank, pack, chunks, index_hash = build_bank()
    report = await run_deterministic_checks(
        bank,
        pack,
        chunks,
        index_hash,
        embedder=_Embedder(),
        target_counts=(1, 1),
        topic_targets={},
        difficulty_targets={},
    )
    checks = {check.name: check for check in report.checks}
    assert not checks["near_duplicates"].ok
    assert report.metrics["max_cosine"] == 1.0


async def test_missing_material_fails_grounding() -> None:
    bank, pack, chunks, index_hash = build_bank()
    bank.items[0] = bank.items[0].model_copy(update={"material_id": "missing"})
    report = await run_deterministic_checks(
        bank,
        pack,
        chunks,
        index_hash,
        target_counts=(1, 1),
        topic_targets={},
        difficulty_targets={},
    )
    checks = {check.name: check for check in report.checks}
    assert not checks["grounding"].ok


def test_committed_calibration_fixture_shape() -> None:
    path = Path(__file__).resolve().parent / "fixtures" / "calibration.jsonl"
    cases = load_calibration(path)
    assert len({case.item_id for case in cases}) == 8
    assert len(cases) == 24
    assert len({case.pass_name for case in cases}) == 3
    assert {case.variant for case in cases} >= {
        "full",
        "partial",
        "wrong",
        "verbose",
        "missing_key_term",
        "off_topic",
        "contradictory",
        "blank",
    }
    assert all(set(case.marks) == {"correctness", "completeness"} for case in cases)
