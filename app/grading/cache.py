"""JSONL cache for judge results (#192).

The cache key is the bank version, item id, answer hash, judge configuration
and rubric content. Only validated, non-needs-review grades are cached. The
file lives under the gitignored data tree; the raw judge response is stored as
a hash for audit.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from app.exam.bank import BankItem
from app.grading.models import JudgeConfig, QuestionGrade

logger = logging.getLogger(__name__)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class JudgeCache:
    """A small append-only cache keyed by item, answer and judge configuration."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self._entries: dict[str, dict] = {}
        if path is not None and path.exists():
            self._load(path)

    @staticmethod
    def key(
        bank_version: str,
        item: BankItem,
        answer_text: str,
        config: JudgeConfig,
    ) -> str:
        rubric = [
            [criterion.criterion_id, criterion.description, criterion.max_marks]
            for criterion in item.rubric
        ]
        payload = [
            bank_version,
            item.item_id,
            _sha256(answer_text),
            config.model,
            config.temperature,
            config.prompt_version,
            config.provider,
            config.max_tokens,
            item.prompt_version,
            rubric,
        ]
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return _sha256(canonical)

    def get(self, key: str, item: BankItem) -> QuestionGrade | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        try:
            grade = QuestionGrade.model_validate(entry["grade"])
        except Exception:  # noqa: BLE001 - a corrupt cache entry is a miss
            logger.warning("ignoring corrupt judge cache entry for %s", item.item_id)
            return None
        if grade.item_id != item.item_id or grade.max_marks != item.marks:
            return None
        if grade.needs_review:
            return None
        return grade

    def set(
        self,
        key: str,
        bank_version: str,
        item: BankItem,
        answer_text: str,
        config: JudgeConfig,
        grade: QuestionGrade,
        raw_sha256: str,
    ) -> None:
        if grade.needs_review or grade.marks_awarded is None:
            raise ValueError("needs_review grades are not cached")
        entry = {
            "key": key,
            "bank_version": bank_version,
            "item_id": item.item_id,
            "rubric_version": item.prompt_version,
            "judge_model": config.model,
            "judge_provider": config.provider,
            "judge_temperature": config.temperature,
            "judge_max_tokens": config.max_tokens,
            "judge_prompt_version": config.prompt_version,
            "answer_sha256": _sha256(answer_text),
            "raw_sha256": raw_sha256,
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "grade": grade.model_dump(mode="json"),
        }
        self._entries[key] = entry
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _load(self, path: Path) -> None:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                key = entry["key"]
                if not isinstance(key, str):
                    raise ValueError("cache key must be a string")
                QuestionGrade.model_validate(entry["grade"])
            except Exception:  # noqa: BLE001 - skip a malformed line
                logger.warning("ignoring corrupt judge cache line %s:%s", path, line_number)
                continue
            self._entries[key] = entry


__all__ = ["JudgeCache"]
