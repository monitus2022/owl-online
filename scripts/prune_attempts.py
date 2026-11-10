"""Prune exam attempts older than the retention window (#180).

The anonymous serving store keeps attempts until the session deletes them
(``DELETE /v1/attempts``) or an operator prunes them. This script is the
documented manual policy; it never touches bank items or grades in place.

Run:
    uv run python scripts/prune_attempts.py --days 90 --dry-run
    uv run python scripts/prune_attempts.py --days 90
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.storage.exam_store import ExamStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=REPO / "data" / "exams" / "exams.db",
    )
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")
    before = (
        (datetime.now(UTC) - timedelta(days=args.days))
        .isoformat()
        .replace("+00:00", "Z")
    )
    with ExamStore(args.db) as store:
        count = store.count_attempts_before(before)
        if args.dry_run:
            print(f"{count} attempts created before {before} would be deleted")
            return 0
        deleted = store.prune_attempts(before)
        print(f"deleted {deleted} attempts created before {before}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
