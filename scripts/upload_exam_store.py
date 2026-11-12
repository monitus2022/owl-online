"""Snapshot, validate and upload the exam store to the private data bucket (#255).

The bank database is gitignored and lives on the host out of band. This takes a
consistent SQLite backup, refuses an empty or partial bank, uploads a
timestamped object plus an `owl-exams.db` alias, and can print a short-lived
presigned URL for the host install.

Run:
    uv run python scripts/upload_exam_store.py --dry-run
    uv run python scripts/upload_exam_store.py --presign

The host install is a separate step: download the presigned URL to
`/data/exams/exams.db`, verify the printed sha256, then recreate the container.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO / "data" / "exams" / "exams.db"
DEFAULT_BUCKET = "monitus-owl-online-data"
DEFAULT_REGION = "ap-northeast-3"
DEFAULT_PREFIX = "deploy"
ALIAS = "owl-exams.db"


class UploadError(ValueError):
    """A store that must not be uploaded as-is."""


@dataclass(frozen=True)
class StoreStats:
    banks: int
    items: int
    attempts: int
    subjects: tuple[str, ...]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _readonly_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def snapshot(source: Path, dest: Path) -> None:
    """Write a consistent single-file copy of a live SQLite store."""
    if not source.is_file():
        raise UploadError(f"exam store not found: {source}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(_readonly_uri(source), uri=True)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()


def validate_snapshot(
    path: Path, *, min_banks: int = 5, allow_attempts: bool = False
) -> StoreStats:
    """Refuse an empty, corrupt or attempt-bearing store before upload."""
    if not path.is_file():
        raise UploadError(f"snapshot not found: {path}")
    conn = sqlite3.connect(_readonly_uri(path), uri=True)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise UploadError(f"integrity check failed: {integrity}")
        violation = conn.execute("PRAGMA foreign_key_check").fetchone()
        if violation is not None:
            raise UploadError(f"foreign key violation: {violation}")
        # Serving selects the latest published version per subject, so a second
        # published version must not make one subject look like two banks.
        banks = conn.execute(
            "SELECT subject, version, mcq_count, short_answer_count FROM banks b "
            "WHERE b.status = 'published' AND b.rowid = ("
            "  SELECT max(b2.rowid) FROM banks b2 "
            "  WHERE b2.subject = b.subject AND b2.status = 'published'"
            ") ORDER BY subject"
        ).fetchall()
        if len(banks) < min_banks:
            raise UploadError(
                f"only {len(banks)} servable subjects; expected at least {min_banks}"
            )
        items = 0
        for subject, version, mcq_count, short_count in banks:
            declared = int(mcq_count) + int(short_count)
            if declared <= 0:
                raise UploadError(f"{subject} {version} declares no questions")
            actual = conn.execute(
                "SELECT count(*) FROM bank_items "
                "WHERE subject = ? AND bank_version = ?",
                (subject, version),
            ).fetchone()[0]
            if actual != declared:
                raise UploadError(
                    f"{subject} {version} declares {declared} items but stores {actual}"
                )
            items += declared
        attempts = conn.execute("SELECT count(*) FROM attempts").fetchone()[0]
    finally:
        conn.close()
    if attempts and not allow_attempts:
        raise UploadError(
            f"snapshot has {attempts} attempts; pass --allow-attempts only if "
            "the host is meant to inherit local session history"
        )
    return StoreStats(
        banks=len(banks),
        items=int(items),
        attempts=int(attempts),
        subjects=tuple(str(row[0]) for row in banks),
    )


def upload(
    path: Path, *, bucket: str, region: str, prefix: str
) -> tuple[str, str]:
    """Upload a timestamped key and copy it to the stable alias."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    key = f"{prefix}/owl-exams-{stamp}.db"
    alias = f"{prefix}/{ALIAS}"
    subprocess.run(
        [
            "aws",
            "s3",
            "cp",
            "--region",
            region,
            "--only-show-errors",
            str(path),
            f"s3://{bucket}/{key}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "aws",
            "s3api",
            "copy-object",
            "--region",
            region,
            "--bucket",
            bucket,
            "--key",
            alias,
            "--copy-source",
            f"{bucket}/{key}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return key, alias


def presign(*, bucket: str, region: str, key: str, expires_in: int) -> str:
    result = subprocess.run(
        [
            "aws",
            "s3",
            "presign",
            "--region",
            region,
            "--expires-in",
            str(expires_in),
            f"s3://{bucket}/{key}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fail(error: subprocess.CalledProcessError, action: str) -> None:
    detail = (error.stderr or "").strip()
    print(f"{action} failed: {detail or error}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE, help="live exam store"
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("OWL_BACKUP_BUCKET", DEFAULT_BUCKET),
        help="private data bucket",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("OWL_BACKUP_REGION", DEFAULT_REGION),
        help="bucket region",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="object key prefix")
    parser.add_argument(
        "--min-banks",
        type=int,
        default=5,
        help="refuse fewer than this many servable subjects (default 5)",
    )
    parser.add_argument(
        "--allow-attempts",
        action="store_true",
        help="allow a snapshot that carries local attempt history",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="snapshot and validate; do not upload"
    )
    parser.add_argument(
        "--presign",
        action="store_true",
        help="print a short-lived GET URL after upload",
    )
    parser.add_argument(
        "--presign-key",
        choices=("timestamped", "alias"),
        default="alias",
        help="which uploaded key to sign (default alias)",
    )
    parser.add_argument(
        "--expires-in",
        type=int,
        default=600,
        help="presigned URL lifetime in seconds (default 600)",
    )
    args = parser.parse_args()

    if args.dry_run and args.presign:
        parser.error("--presign cannot be combined with --dry-run")
    if args.presign and not 60 <= args.expires_in <= 43200:
        parser.error("--expires-in must be between 60 and 43200 seconds")

    with tempfile.TemporaryDirectory(prefix="owl-exam-upload-") as staging:
        snap = Path(staging) / "exams.db"
        try:
            snapshot(args.source, snap)
            stats = validate_snapshot(
                snap,
                min_banks=args.min_banks,
                allow_attempts=args.allow_attempts,
            )
        except (UploadError, sqlite3.Error, OSError) as error:
            print(f"refusing upload: {error}", file=sys.stderr)
            return 1

        digest = sha256(snap)
        size_mb = snap.stat().st_size / 1e6
        print(
            f"store: {stats.banks} servable subjects, {stats.items} items, "
            f"{stats.attempts} attempts; {size_mb:.2f} MB"
        )
        print(f"subjects: {', '.join(stats.subjects)}")
        print(f"sha256: {digest}")
        if stats.attempts:
            print("warning: uploading local attempt history", file=sys.stderr)

        if args.dry_run:
            print("dry-run: not uploaded")
            return 0

        try:
            key, alias = upload(
                snap,
                bucket=args.bucket,
                region=args.region,
                prefix=args.prefix,
            )
        except subprocess.CalledProcessError as error:
            _fail(error, "upload")
            return 1
        print(f"uploaded: s3://{args.bucket}/{key}")
        print(f"alias:    s3://{args.bucket}/{alias}")

        if args.presign:
            target = key if args.presign_key == "timestamped" else alias
            try:
                url = presign(
                    bucket=args.bucket,
                    region=args.region,
                    key=target,
                    expires_in=args.expires_in,
                )
            except subprocess.CalledProcessError as error:
                _fail(error, "presign")
                return 1
            print(f"url: {url}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
