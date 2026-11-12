"""Deterministic API stub for the Playwright E2E suite (#179).

The real corpus, index and pack prose are not in git, so the browser suite
runs against the real FastAPI app with an injected runtime: the real router,
graph, SSE contract and schemas, but a tiny in-memory pack and a fixed LLM.
No model keys and no private data.

Run:
    uv run python e2e/api_server.py
"""

# ruff: noqa: E402 - the repo root goes on sys.path before the app imports.

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import uvicorn  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from app.agent import build_graph  # noqa: E402
from app.agent.memory import memory_saver  # noqa: E402
from app.agent.persona import PERSONAS
from app.api.runtime import Runtime
from app.config import Settings
from app.exam.bank import ExamBank  # noqa: E402
from app.knowledge import load_lore
from app.knowledge.materials import Material, SourceRef, chunk_text_hash
from app.knowledge.packs import (
    Concept,
    PackManifest,
    PackStore,
    PackSummary,
    SubjectPack,
    Topic,
)
from app.main import create_app
from app.schemas import Chunk, ChunkMetadata  # noqa: E402
from app.storage.exam_store import ExamStore  # noqa: E402
from eval.exam.fixtures import build_bank  # noqa: E402

CHUNK_ID = "b1-c01-0000"
MATERIAL_ID = "dada-test-material"
TEXT = "A Boggart takes the shape of what the watcher fears most."
ANSWER = (
    "A Boggart is a shape-shifter that takes the shape of what the watcher "
    f"fears most. [mat:{MATERIAL_ID}] [{CHUNK_ID}]."
)


class StubRetriever:
    async def retrieve(self, query: str, top_k: int) -> list[Chunk]:
        return [
            Chunk(
                id=CHUNK_ID,
                text=TEXT,
                metadata=ChunkMetadata(
                    book_num=1,
                    chapter_num=1,
                    book_name="Book 1",
                    chapter_name="Chapter 1",
                ),
                score=1.0,
            )
        ]


class StubLlm:
    name = "e2e/stub"

    @staticmethod
    def _answer(prompt: str) -> str:
        # The memory spec asks "Who is Professor Lupin?" then "who trained
        # him?". The second prompt only names Lupin when the resolver replaced
        # the pronoun, so this branch proves the thread carried the entity.
        lowered = prompt.lower()
        if "who trained" in lowered and "lupin" in lowered:
            return f"Remus Lupin trained Professor Lupin [mat:{MATERIAL_ID}] [{CHUNK_ID}]."
        if "lupin" in lowered:
            return (
                "Professor Lupin taught Defence Against the Dark Arts "
                f"[mat:{MATERIAL_ID}] [{CHUNK_ID}]."
            )
        return ANSWER

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        return self._answer(prompt)

    async def stream(self, system: str, prompt: str, *, context=None):
        for piece in self._answer(prompt).split(" "):
            yield piece + " "


class StubSelector:
    def __init__(self, material: Material) -> None:
        self.material = material

    async def select(
        self,
        question: str,
        *,
        subject: str,
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> list[Material]:
        return [self.material]

    def subjects(self) -> tuple[str, ...]:
        return ("dada",)

    def concept_terms(self, subject: str) -> set[str]:
        return {"boggart", "counter-jinx", "charm", "defence"}


def _material() -> Material:
    return Material(
        material_id=MATERIAL_ID,
        subject="dada",
        topic="dark-creatures",
        concept="dada-creature-boggart",
        kind="creature",
        text=TEXT,
        review_status="reviewed",
        source_refs=[
            SourceRef(
                chunk_id=CHUNK_ID,
                book=1,
                chapter=1,
                quote="A Boggart takes the shape",
                text_hash=chunk_text_hash(TEXT),
                index_text_hash="e2e-index",
            )
        ],
    )


def _pack(material: Material) -> SubjectPack:
    return SubjectPack(
        manifest=PackManifest(
            subject="dada",
            version="1.0.0",
            status="published",
            index_text_hash="e2e-index",
        ),
        topics=[Topic(topic_id="dark-creatures", subject="dada", title="Dark creatures")],
        concepts=[
            Concept(
                concept_id="dada-creature-boggart",
                subject="dada",
                kind="creature",
                title="Boggart",
            )
        ],
        materials=[material],
    )


class StubJudge:
    """One deterministic judge call: every rubric criterion is fully awarded."""

    async def generate(self, system: str, prompt: str, *, context=None) -> str:
        data = json.loads(prompt)
        results = {}
        for question in data["questions"]:
            evidence = question["evidence"][0]["chunk_id"]
            results[question["item_id"]] = {
                "criteria": [
                    {
                        "criterion_id": criterion["criterion_id"],
                        "awarded": criterion["max_marks"],
                        "max_marks": criterion["max_marks"],
                        "reason": "Met.",
                    }
                    for criterion in question["rubric"]
                ],
                "total": question["max_marks"],
                "feedback": "Met.",
                "evidence_ids": [evidence],
            }
        return json.dumps({"results": results})

    def stream(self, system: str, prompt: str, *, context=None):
        async def gen():
            yield ""

        return gen()


def _exam_bank() -> ExamBank:
    """A tiny published bank: six MCQ and four short answers from the fixture."""
    bank, _, _, _ = build_bank()
    mcq, short = bank.items[0], bank.items[1]
    mcqs = [
        mcq.model_copy(
            update={
                "item_id": f"dada-mcq-{index:03d}",
                "prompt": f"Sample MCQ {index}?",
            }
        )
        for index in range(1, 7)
    ]
    shorts = [
        short.model_copy(
            update={
                "item_id": f"dada-short-{index:03d}",
                "prompt": f"Sample short answer {index}?",
            }
        )
        for index in range(1, 5)
    ]
    manifest = bank.manifest.model_copy(
        update={"mcq_count": 6, "short_answer_count": 4}
    )
    return ExamBank(manifest=manifest, items=[*mcqs, *shorts])


def build_app():
    material = _material()
    pack = _pack(material)
    store = PackStore(packs={"dada": pack}, fingerprints={"dada": "e2e"})
    selector = StubSelector(material)
    lore = load_lore(REPO / "eval" / "fixtures" / "lore")
    retriever = StubRetriever()
    llm = StubLlm()

    def graph(checkpointer: MemorySaver | None):
        return build_graph(
            retriever,
            llm,
            lesson=selector,
            lesson_subject="dada",
            lesson_top_k=3,
            personas=PERSONAS,
            default_subject="dada",
            lore=lore,
            checkpointer=checkpointer,
        )

    agent = graph(memory_saver())
    stateless_agent = graph(None)
    summary = PackSummary(
        subject="dada",
        title="Defense Against the Dark Arts",
        tier="owl",
        version="1.0.0",
        status="published",
        built_at="2026-11-11T00:00:00Z",
        fingerprint="e2e",
        topics=("dark-creatures",),
        concepts=1,
        materials=1,
    )
    exam_bank = _exam_bank()
    exam_store = ExamStore(
        Path(tempfile.mkdtemp(prefix="owl-e2e-exams-")) / "exams.db"
    )
    exam_store.replace_bank(exam_bank)
    runtime = Runtime(
        retriever=retriever,
        llm=llm,
        agent=agent,
        stateless_agent=stateless_agent,
        packs=(summary,),
        pack_store=store,
        lesson=selector,
        lore=lore,
        exam_store=exam_store,
        exam_judges={exam_bank.manifest.judge_model: StubJudge()},
    )
    settings = Settings(
        lesson_mode=True,
        persona=True,
        lesson_fallback=True,
        session_secret="e2e-session-secret",
        cors_origins="http://127.0.0.1:5500,http://localhost:5500",
        chat_per_minute=1000,
        chat_per_day=10000,
        chat_ip_per_day=10000,
        chat_concurrent=32,
        exam_attempts_per_day_anonymous=1000,
        exam_attempts_per_day_signed_in=1000,
        exam_attempts_per_day_ip=1000,
    )
    return create_app(app_settings=settings, runtime=runtime)


def main() -> None:
    uvicorn.run(
        build_app(),
        host="127.0.0.1",
        port=8001,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
