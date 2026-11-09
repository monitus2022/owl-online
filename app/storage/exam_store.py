"""SQLite serving store for validated exam banks (#189).

The authoring source is `data/exams/<subject>/bank.jsonl`. This store is a
deterministic import of that file, not a second source of truth. It exposes the
manifest and items as the Pydantic records from `app.exam.bank` so the serving
layer never needs the JSONL layout.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.exam.bank import BankItem, BankManifest, ExamBank

_SCHEMA = """
CREATE TABLE IF NOT EXISTS banks (
    subject TEXT NOT NULL,
    version TEXT NOT NULL,
    tier TEXT NOT NULL,
    status TEXT NOT NULL,
    built_at TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT '',
    pack_version TEXT NOT NULL,
    pack_fingerprint TEXT NOT NULL,
    index_text_hash TEXT NOT NULL,
    generator_model TEXT NOT NULL,
    generator_temperature REAL,
    generator_prompt_version TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    judge_temperature REAL,
    judge_prompt_version TEXT NOT NULL,
    mcq_count INTEGER NOT NULL,
    short_answer_count INTEGER NOT NULL,
    PRIMARY KEY (subject, version)
);

CREATE TABLE IF NOT EXISTS bank_items (
    subject TEXT NOT NULL,
    bank_version TEXT NOT NULL,
    item_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    prompt TEXT NOT NULL,
    topic TEXT NOT NULL,
    concepts_json TEXT NOT NULL,
    material_id TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    marks INTEGER NOT NULL,
    rubric_json TEXT NOT NULL,
    required_points_json TEXT NOT NULL,
    model_answer TEXT,
    options_json TEXT NOT NULL,
    correct_option_id TEXT,
    rationale TEXT,
    review_status TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    canon_tier TEXT NOT NULL,
    PRIMARY KEY (subject, bank_version, item_id),
    FOREIGN KEY (subject, bank_version) REFERENCES banks(subject, version) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS bank_items_item_id ON bank_items(item_id);
CREATE INDEX IF NOT EXISTS bank_items_kind ON bank_items(subject, bank_version, kind);
"""

_MANIFEST_COLUMNS = (
    "subject",
    "version",
    "tier",
    "status",
    "built_at",
    "reviewed_at",
    "pack_version",
    "pack_fingerprint",
    "index_text_hash",
    "generator_model",
    "generator_temperature",
    "generator_prompt_version",
    "judge_model",
    "judge_temperature",
    "judge_prompt_version",
    "mcq_count",
    "short_answer_count",
)

_ITEM_COLUMNS = (
    "subject",
    "bank_version",
    "item_id",
    "kind",
    "prompt",
    "topic",
    "concepts_json",
    "material_id",
    "source_refs_json",
    "evidence_json",
    "difficulty",
    "marks",
    "rubric_json",
    "required_points_json",
    "model_answer",
    "options_json",
    "correct_option_id",
    "rationale",
    "review_status",
    "prompt_version",
    "canon_tier",
)


class ExamStore:
    """A small sqlite repository for validated bank manifests and items."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        """Add manifest columns introduced after the first serving schema."""
        columns = {
            str(row["name"])
            for row in self._conn.execute("PRAGMA table_info(banks)")
        }
        additions = {
            "reviewed_at": "TEXT NOT NULL DEFAULT ''",
            "generator_temperature": "REAL",
            "judge_temperature": "REAL",
        }
        for name, ddl in additions.items():
            if name not in columns:
                self._conn.execute(f"ALTER TABLE banks ADD COLUMN {name} {ddl}")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ExamStore:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def replace_bank(self, bank: ExamBank, *, force: bool = False) -> None:
        """Replace one subject/version atomically.

        A published version is immutable unless `force=True`; a paper or attempt
        may already point at its item ids.
        """
        existing = self.manifest(bank.manifest.subject, bank.manifest.version)
        if existing is not None and existing.status == "published" and not force:
            raise ValueError(
                f"{bank.manifest.subject} {bank.manifest.version} is published; "
                "pass force=True to replace it"
            )
        counts = bank.counts()
        manifest = bank.manifest.model_copy(
            update={
                "mcq_count": counts["mcq"],
                "short_answer_count": counts["short_answer"],
            }
        )
        item_rows = [self._item_row(manifest, item) for item in bank.items]
        with self._conn:
            self._conn.execute(
                "DELETE FROM bank_items WHERE subject = ? AND bank_version = ?",
                (manifest.subject, manifest.version),
            )
            self._conn.execute(
                "DELETE FROM banks WHERE subject = ? AND version = ?",
                (manifest.subject, manifest.version),
            )
            self._conn.execute(
                f"INSERT INTO banks ({', '.join(_MANIFEST_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in _MANIFEST_COLUMNS)})",
                tuple(getattr(manifest, column) for column in _MANIFEST_COLUMNS),
            )
            if item_rows:
                self._conn.executemany(
                    f"INSERT INTO bank_items ({', '.join(_ITEM_COLUMNS)}) "
                    f"VALUES ({', '.join('?' for _ in _ITEM_COLUMNS)})",
                    item_rows,
                )

    def manifest(self, subject: str, version: str | None = None) -> BankManifest | None:
        if version is None:
            row = self._conn.execute(
                "SELECT * FROM banks WHERE subject = ? ORDER BY rowid DESC LIMIT 1",
                (subject,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM banks WHERE subject = ? AND version = ?",
                (subject, version),
            ).fetchone()
        return None if row is None else self._manifest_from_row(row)

    def items(
        self,
        subject: str,
        version: str | None = None,
        kind: str | None = None,
    ) -> list[BankItem]:
        manifest = self.manifest(subject, version)
        if manifest is None:
            return []
        sql = "SELECT * FROM bank_items WHERE subject = ? AND bank_version = ?"
        params: list[str] = [subject, manifest.version]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY item_id"
        return [self._item_from_row(row) for row in self._conn.execute(sql, params)]

    def item(
        self,
        item_id: str,
        subject: str | None = None,
        version: str | None = None,
    ) -> BankItem | None:
        if subject is None:
            row = self._conn.execute(
                "SELECT * FROM bank_items WHERE item_id = ? ORDER BY bank_version DESC LIMIT 1",
                (item_id,),
            ).fetchone()
        elif version is None:
            manifest = self.manifest(subject)
            if manifest is None:
                return None
            row = self._conn.execute(
                "SELECT * FROM bank_items WHERE item_id = ? AND subject = ? AND bank_version = ?",
                (item_id, subject, manifest.version),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM bank_items WHERE item_id = ? AND subject = ? AND bank_version = ?",
                (item_id, subject, version),
            ).fetchone()
        return None if row is None else self._item_from_row(row)

    def counts(self, subject: str, version: str | None = None) -> dict[str, int]:
        manifest = self.manifest(subject, version)
        if manifest is None:
            return {"mcq": 0, "short_answer": 0}
        return {"mcq": manifest.mcq_count, "short_answer": manifest.short_answer_count}

    def versions(self, subject: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT version FROM banks WHERE subject = ? ORDER BY rowid",
            (subject,),
        ).fetchall()
        return [str(row["version"]) for row in rows]

    @staticmethod
    def _manifest_from_row(row: sqlite3.Row) -> BankManifest:
        return BankManifest.model_validate({column: row[column] for column in _MANIFEST_COLUMNS})

    @staticmethod
    def _item_row(manifest: BankManifest, item: BankItem) -> tuple[object, ...]:
        return (
            manifest.subject,
            manifest.version,
            item.item_id,
            item.kind,
            item.prompt,
            item.topic,
            json.dumps(list(item.concepts)),
            item.material_id,
            json.dumps([ref.model_dump(mode="json") for ref in item.source_refs]),
            json.dumps(item.evidence_snapshot.model_dump(mode="json")),
            item.difficulty,
            item.marks,
            json.dumps([criterion.model_dump(mode="json") for criterion in item.rubric]),
            json.dumps(list(item.required_points)),
            item.model_answer,
            json.dumps([option.model_dump(mode="json") for option in item.options]),
            item.correct_option_id,
            item.rationale,
            item.review_status,
            item.prompt_version,
            item.canon_tier,
        )

    @staticmethod
    def _item_from_row(row: sqlite3.Row) -> BankItem:
        return BankItem.model_validate(
            {
                "item_id": row["item_id"],
                "subject": row["subject"],
                "kind": row["kind"],
                "prompt": row["prompt"],
                "topic": row["topic"],
                "concepts": json.loads(row["concepts_json"]),
                "material_id": row["material_id"],
                "source_refs": json.loads(row["source_refs_json"]),
                "evidence_snapshot": json.loads(row["evidence_json"]),
                "difficulty": row["difficulty"],
                "marks": row["marks"],
                "rubric": json.loads(row["rubric_json"]),
                "required_points": json.loads(row["required_points_json"]),
                "model_answer": row["model_answer"],
                "options": json.loads(row["options_json"]),
                "correct_option_id": row["correct_option_id"],
                "rationale": row["rationale"],
                "review_status": row["review_status"],
                "prompt_version": row["prompt_version"],
                "canon_tier": row["canon_tier"],
            }
        )


__all__ = ["ExamStore"]
