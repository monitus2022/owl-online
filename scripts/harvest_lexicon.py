"""Lexicon harvest CLI (#126): discover, fetch politely, parse to JSONL.

Run:
    uv run python scripts/harvest_lexicon.py --discover-only
    uv run python scripts/harvest_lexicon.py --limit 40      # smoke run
    uv run python scripts/harvest_lexicon.py                 # full crawl

Params and wiring only; the logic lives in `app/pipeline/ingest/lexicon`.
Output: `data/lexicon/*.jsonl` (local only, gitignored). The politeness rule
is one request per second plus jitter; cache hits make a resume free.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.ingest.lexicon.discovery import (  # noqa: E402
    SITEMAPS,
    QueueItem,
    build_queue,
    parse_locs,
)
from app.pipeline.ingest.lexicon.fetch import USER_AGENT, Fetcher  # noqa: E402
from app.pipeline.ingest.lexicon.harvest import harvest  # noqa: E402

DATA_DIR = REPO / "data/lexicon"


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover-only", action="store_true", help="write the queue and stop")
    parser.add_argument("--limit", type=int, default=0, help="harvest only the first N queue items")
    parser.add_argument(
        "--reuse-queue", action="store_true", help="skip discovery, read work_queue.jsonl"
    )
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    queue_path = DATA_DIR / "work_queue.jsonl"

    fetcher = Fetcher(DATA_DIR / "pages", opener=http_get)
    if args.reuse_queue and queue_path.exists():
        queue = [
            QueueItem(**json.loads(line)) for line in queue_path.read_text().splitlines()
        ]
    else:
        sitemap_bodies = {}
        for name, url in SITEMAPS.items():
            sitemap_bodies[name] = http_get(url).decode("utf-8", errors="replace")
            print(f"discovered {name}: {len(parse_locs(sitemap_bodies[name]))} urls")
        queue = build_queue(sitemap_bodies)
        queue_path.write_text(
            "\n".join(json.dumps(vars(item)) for item in queue) + "\n", encoding="utf-8"
        )
    print(f"work queue: {len(queue)} urls -> {queue_path}")
    if args.discover_only:
        return 0

    if args.limit:
        queue = queue[: args.limit]

    def progress(done: int, total: int) -> None:
        if done % 50 == 0 or done == total:
            print(f"progress: {done}/{total}", flush=True)

    summary = harvest(queue, DATA_DIR, fetcher, progress=progress)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
