"""Run the persona-conformance eval (#176).

The command needs the host corpus, the DADA pack and model keys because the
pack prose and corpus are not in git. It compares the pre-#176 lesson prompt
with the persona-first prompt on the same fixture, then prints the record
summary.

Run:
    uv run python scripts/run_persona_eval.py
    uv run python scripts/run_persona_eval.py --no-calibration
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

from app.agent.persona import PERSONA  # noqa: E402
from app.api.runtime import build_runtime  # noqa: E402
from app.config import Settings  # noqa: E402
from app.pipeline.index.builder import load_chunks  # noqa: E402
from app.providers.factory import make_llm  # noqa: E402
from eval.harness import JUDGE_MODEL, CachedLlm  # noqa: E402
from eval.persona import (  # noqa: E402
    PersonaEvalStack,
    load_calibration,
    load_persona_scenarios,
    render_report,
    run_calibration,
    run_persona_eval,
)
from eval.results import timestamp_run_id  # noqa: E402


def _fixture_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


async def _run(args: argparse.Namespace) -> int:
    settings = Settings(persona=True, lesson_mode=True, lesson_fallback=True)
    runtime = await build_runtime(settings)
    generator = None
    judge_llm = None
    try:
        if runtime.lesson is None or runtime.pack_store is None:
            print("lesson selector is not available; is the DADA pack published?")
            return 2
        pack = runtime.pack_store.get(settings.lore_subject)
        if pack is None:
            print(f"no published pack for {settings.lore_subject}")
            return 2
        scenarios = load_persona_scenarios(args.fixture)
        chunks = load_chunks(settings.chunks_path)
        chunks_by_id = {chunk.id: chunk for chunk in chunks}
        generator = make_llm(settings.provider, temperature=args.temperature)
        judge_llm = make_llm("openrouter", model=JUDGE_MODEL, temperature=0.0)
        cache_dir = args.cache_dir or settings.chunks_path.parent / "persona_eval_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        judge = CachedLlm(
            judge_llm,
            JUDGE_MODEL,
            cache_dir,
            variant="persona-judge-temperature=0",
        )

        calibration = None
        if not args.no_calibration:
            calibration = await run_calibration(
                load_calibration(args.calibration), judge, persona=PERSONA
            )

        stack = PersonaEvalStack(
            persona=PERSONA,
            selector=runtime.lesson,
            retriever=runtime.retriever,
            llm_for_sample=lambda sample: CachedLlm(
                generator,
                generator.name,
                cache_dir,
                variant=f"persona-eval-sample={sample}",
            ),
            judge=judge,
            pack=pack,
            chunks_by_id=chunks_by_id,
            subject=settings.lore_subject,
            lore=runtime.lore,
            lesson_top_k=settings.lesson_top_k,
            lesson_min_score=settings.lesson_min_score,
            lesson_fallback=settings.lesson_fallback,
            max_retries=settings.retry_budget,
        )
        report = await run_persona_eval(
            scenarios,
            stack,
            samples=args.samples,
            generator_model=generator.name,
            judge_model=JUDGE_MODEL,
            judge_temperature=0.0,
            fixture_sha=_fixture_sha(args.fixture),
            calibration=calibration,
        )
        run_id = timestamp_run_id()
        print(f"run_id: {run_id}")
        print(render_report(report))
        out = args.json or REPO / "eval" / "results" / f"persona-{run_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "report": dataclasses.asdict(report),
        }
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {out}")
        return 0 if report.ok else 1
    finally:
        await runtime.aclose()
        for client in (generator, judge_llm):
            close = getattr(client, "aclose", None)
            if close is not None:
                await close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=REPO / "eval" / "persona" / "fixtures" / "conformance.jsonl",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=REPO / "eval" / "persona" / "fixtures" / "calibration.jsonl",
    )
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--no-calibration", action="store_true")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
