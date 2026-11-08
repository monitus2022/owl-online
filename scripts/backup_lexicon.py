"""Back up gitignored corpus and lexicon artifacts to the private bucket.

Tar + `aws s3 cp` to s3://$OWL_BACKUP_BUCKET (default monitus-owl-online-data),
mirroring the existing owl-data.tgz convention. Both bundles are private
backups of locally-held artifacts; nothing is republished. The lexicon bundle
carries the site's HTML fetch cache (copyrighted prose) under the same private
posture as the books corpus: bucket reads are owner-only, serving stays on the
host volume.

  uv run python scripts/backup_lexicon.py --what data --dry-run
  uv run python scripts/backup_lexicon.py --what all
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
DEFAULT_BUCKET = "monitus-owl-online-data"
DEFAULT_REGION = "ap-northeast-3"

DATA_MEMBERS = [
    "chunks.jsonl",
    "chunks_context.jsonl",
    "rerank_cache.jsonl",
    "index/chroma",
    "lore",
    "subjects",
]
LEXICON_DIR = "lexicon"
LEXICON_NAME = "owl-lexicon"
DATA_NAME = "owl-data"
SKIP_IF_MISSING = {"subjects", "lore"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_tar(kind: str, staging: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    name = LEXICON_NAME if kind == "lexicon" else DATA_NAME
    out = staging / f"{name}-{stamp}.tgz"
    if kind == "lexicon":
        if not (DATA / LEXICON_DIR).is_dir():
            raise SystemExit(f"missing {DATA / LEXICON_DIR}; finish the harvest first")
        members = [f"{LEXICON_DIR}"]
    else:
        members = []
        for member in DATA_MEMBERS:
            if not (DATA / member).exists():
                if member in SKIP_IF_MISSING:
                    print(f"skip {member}: not present")
                    continue
                raise SystemExit(f"missing required artifact: {DATA / member}")
            members.append(member)
    # -h follows symlinked artifacts so a worktree pointing at the host data
    # dir archives real contents, not link entries (the 0-byte backup trap).
    subprocess.run(
        ["tar", "-h", "-czf", str(out), "-C", str(REPO),
         *(f"data/{m}" for m in members)],
        check=True,
    )
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
