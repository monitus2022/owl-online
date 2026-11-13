"""Run the lesson faithfulness calibration (#258).

The labels in the fixture are agent-proposed until the owner adopts them. This
command measures judge agreement; it does not change the production metric.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.config import Settings  # noqa: E402
from eval.harness import JUDGE_MODEL  # noqa: E402
from eval.rag.calibration import (  # noqa: E402
    load_calibration,
    render_calibration,
    run_calibration,
)
from eval.rag.runner import EVAL_TEMPERATURE, build_stack  # noqa: E402
from eval.results import timestamp_run_id  # noqa: E402

PROMPT_VERSION = "faithfulness-label-v1"


async def _run(args: argparse.Namespace) -> int:
    settings = Settings(persona=True, lesson_mode=True, lesson_fallback=True)
    stack = await build_stack(settings, args.cache)
    try:
        items = load_calibration(args.calibration)
        report = await run_calibration(items, stack)
    finally:
        await stack.aclose()
    run_id = timestamp_run_id()
    fixture_sha = hashlib.sha256(args.calibration.read_bytes()).hexdigest()[:12]
    print(f"run_id: {run_id}")
    print(f"fixture sha: {fixture_sha}")
    print(render_calibration(report))
    out = args.json or args.results / f"rag-calibration-{run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "judge": JUDGE_MODEL,
                "judge_temperature": EVAL_TEMPERATURE,
                "prompt_version": PROMPT_VERSION,
                "fixture_sha": fixture_sha,
                "settings": {
                    "provider": settings.provider,
                    "embedder_provider": settings.embedder_provider,
                    "lesson_top_k": settings.lesson_top_k,
                    "lesson_min_score": settings.lesson_min_score,
                    "lesson_fallback": settings.lesson_fallback,
                },
                "report": dataclasses.asdict(report),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}")
    return 0 if report.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the lesson faithfulness calibration")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=REPO / "eval" / "rag" / "fixtures" / "faithfulness_calibration.jsonl",
    )
    parser.add_argument("--cache", type=Path, default=REPO / "eval" / ".cache" / "rag")
    parser.add_argument("--results", type=Path, default=REPO / "eval" / "results")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
