"""Back up gitignored corpus, lexicon and serving artifacts to the private bucket.

Tar + `aws s3 cp` to s3://$OWL_BACKUP_BUCKET (default monitus-owl-online-data),
mirroring the existing owl-data.tgz convention. Both bundles are private
backups of locally-held artifacts; nothing is republished. The lexicon bundle
carries the site's HTML fetch cache (copyrighted prose) under the same private
posture as the books corpus: bucket reads are owner-only, serving stays on the
host volume. The data bundle includes the exam store, which is also gitignored
and cannot be rebuilt from the image; that member is snapshotted consistently
and may carry attempt history by design. Use `upload_exam_store.py` for the
serving copy. `--what data` requires a local exam store, so a checkout without
one must build or restore it first.

  uv run python scripts/backup_lexicon.py --what data --dry-run
  uv run python scripts/backup_lexicon.py --what all
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.upload_exam_store import (  # noqa: E402
    DEFAULT_BUCKET,
    DEFAULT_REGION,
    sha256,
    snapshot,
)

DATA = REPO / "data"

DATA_MEMBERS = [
    "chunks.jsonl",
    "chunks_context.jsonl",
    "rerank_cache.jsonl",
    "index/chroma",
    "lore",
    "subjects",
    "exams/exams.db",
]
LEXICON_DIR = "lexicon"
LEXICON_NAME = "owl-lexicon"
DATA_NAME = "owl-data"
SKIP_IF_MISSING = {"subjects", "lore"}


def build_tar(kind: str, staging: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    name = LEXICON_NAME if kind == "lexicon" else DATA_NAME
    out = staging / f"{name}-{stamp}.tgz"
    if kind == "lexicon":
        if not (DATA / LEXICON_DIR).is_dir():
            raise SystemExit(f"missing {DATA / LEXICON_DIR}; finish the harvest first")
        # -h follows symlinked artifacts so a worktree pointing at the host data
        # dir archives real contents, not link entries (the 0-byte backup trap).
        subprocess.run(
            ["tar", "-h", "-czf", str(out), "-C", str(REPO), f"data/{LEXICON_DIR}"],
            check=True,
        )
        return out
    members = []
    for member in DATA_MEMBERS:
        if not (DATA / member).exists():
            if member in SKIP_IF_MISSING:
                print(f"skip {member}: not present")
                continue
            raise SystemExit(f"missing required artifact: {DATA / member}")
        members.append(member)
    # The exam store is a live SQLite database; snapshot it before tarring so a
    # backup taken while a grade commits cannot restore as a corrupt file. The
    # other members are symlinked and tar -h dereferences them.
    tree = staging / "data"
    tree.mkdir(parents=True, exist_ok=True)
    for member in members:
        target = DATA / member
        link = tree / member
        link.parent.mkdir(parents=True, exist_ok=True)
        if member == "exams/exams.db":
            snapshot(target, link)
        else:
            if link.is_symlink():
                link.unlink()
            link.symlink_to(target)
    subprocess.run(["tar", "-h", "-czf", str(out), "-C", str(staging), "data"], check=True)
    return out


def upload(bundle: Path, bucket: str, region: str) -> tuple[str, str]:
    alias = "-".join(bundle.stem.split("-")[:-1])
    ts_key = f"s3://{bucket}/{bundle.name}"
    alias_key = f"s3://{bucket}/{alias}.tgz"
    for key in (ts_key, alias_key):
        subprocess.run(
            ["aws", "s3", "cp", "--only-show-errors", "--region", region,
             str(bundle), key],
            check=True,
        )
    return ts_key, alias_key


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--what", choices=["lexicon", "data", "all"], default="all")
    parser.add_argument("--bucket", default=os.environ.get("OWL_BACKUP_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--region", default=os.environ.get("OWL_BACKUP_REGION", DEFAULT_REGION))
    parser.add_argument("--dry-run", action="store_true", help="build and hash; do not upload")
    parser.add_argument(
        "--min-mb",
        type=float,
        default=10.0,
        help="refuse to upload a bundle smaller than this (empty-bundle guard)",
    )
    args = parser.parse_args()

    kinds = ["lexicon", "data"] if args.what == "all" else [args.what]
    staging = Path(tempfile.mkdtemp(prefix="owl-backup-"))
    try:
        for kind in kinds:
            bundle = build_tar(kind, staging)
            size_mb = bundle.stat().st_size / 1e6
            digest = sha256(bundle)
            print(f"{kind}: {bundle.name} ({size_mb:.1f} MB) sha256={digest[:16]}")
            if size_mb < args.min_mb:
                raise SystemExit(
                    f"bundle is {size_mb:.1f} MB < --min-mb {args.min_mb}; "
                    "refusing to upload (are the artifacts real files, not symlinks?)"
                )
            if args.dry_run:
                print("  dry-run: not uploaded")
                continue
            ts_key, alias_key = upload(bundle, args.bucket, args.region)
            print(f"  uploaded {ts_key}\n  alias    {alias_key}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
