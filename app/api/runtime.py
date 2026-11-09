"""Composition root: build the contract objects once, at app startup.

The API receives wired contracts and never builds a provider per request.
"""

import logging
from dataclasses import dataclass

from langgraph.graph.state import CompiledStateGraph

from app.agent import build_graph
from app.agent.persona import PERSONA
from app.config import Settings
from app.knowledge import LoreStore, load_lore
from app.knowledge.lesson import LessonSelector
from app.knowledge.packs import PackStore, PackSummary, load_pack_store
from app.pipeline.retrieve import compose_retriever
from app.providers.contracts import Llm, Retriever
from app.providers.factory import make_embedder, make_llm, make_reranker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Runtime:
    """Wired contracts the API serves requests with."""

    retriever: Retriever
    llm: Llm
    agent: CompiledStateGraph | None = None
    index_hash: str = "unknown-index"
    small_llm: Llm | None = None
    lore: LoreStore | None = None
    packs: tuple[PackSummary, ...] = ()
    pack_store: PackStore | None = None
    lesson: LessonSelector | None = None

    async def aclose(self) -> None:
        """Release provider clients on shutdown (embedder pool, model client)."""
        seen: set[int] = set()
        for component in (self.retriever, self.llm, self.small_llm):
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
            close = getattr(component, "aclose", None)
            if close is not None:
                await close()


def lesson_available(settings: Settings, runtime: Runtime) -> bool:
    """One definition for the payload flag and the request gate.

    Lesson is available only when the feature is on, a selector exists, and the
    configured subject is one the selector can actually serve.
    """
    return (
        settings.lesson_mode
        and runtime.lesson is not None
        and settings.lore_subject in runtime.lesson.subjects()
    )

    async def aclose(self) -> None:
        """Release provider clients on shutdown (embedder pool, model client)."""
        seen: set[int] = set()
        for component in (self.retriever, self.llm, self.small_llm):
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
            close = getattr(component, "aclose", None)
            if close is not None:
                await close()


async def build_runtime(settings: Settings) -> Runtime:
    """Load the local hybrid index and build the configured model adapters."""
    reranker = (
        None if settings.rerank_provider == "none" else make_reranker(settings.rerank_provider)
    )
    embedder = make_embedder(settings.embedder_provider)
    setup = await compose_retriever(
        settings.chunks_path,
        settings.index_dir,
        embedder,
        reranker=reranker,
        pool=settings.rerank_pool if reranker is not None else None,
        min_score=settings.rerank_min_score,
        subquery_quota=settings.subquery_quota,
    )
    if settings.multi_book and settings.persona:
        logger.warning(
            "OWL_MULTI_BOOK and OWL_PERSONA are both on; the multi-book path "
            "ignores the persona suffix"
        )
    lore: LoreStore | None = None
    if settings.lore_path is not None and settings.lore_path.exists():
        lore = load_lore(settings.lore_path)
        logger.info(
            "lore pack loaded: %d entries from %s",
            len(lore.entries),
            settings.lore_path,
        )
    else:
        logger.info(
            "lore pack absent at %s; answers stay book-only", settings.lore_path
        )
    packs: tuple[PackSummary, ...] = ()
    pack_store: PackStore | None = None
    lesson: LessonSelector | None = None
    if settings.subjects_path is not None and settings.subjects_path.is_dir():
        pack_store = load_pack_store(
            settings.subjects_path, setup.chunks_by_id, setup.text_hash
        )
        packs = tuple(pack_store.summaries())
        logger.info(
            "subject packs loaded: %s",
            [f"{pack.subject} {pack.version}" for pack in packs] or "none",
        )
        if settings.lesson_mode and packs:
            try:
                lesson = await LessonSelector.build(pack_store, embedder)
            except Exception as error:
                # Lesson mode is additive. A failed startup embedding must not
                # take the corpus chat path down with it; the API gate then
                # answers 400 for lesson requests.
                logger.warning("lesson mode disabled: selector build failed: %s", error)
            else:
                logger.info(
                    "lesson mode enabled: %s",
                    list(lesson.subjects()) or "no subject vectors",
                )
    else:
        logger.info(
            "subject packs absent at %s; the subject index stays empty",
            settings.subjects_path,
        )
    llm = make_llm(settings.provider)
    small_llm = (
        make_llm(settings.small_provider, model=settings.small_model)
        if settings.routing == "intent"
        else None
    )
    return Runtime(
        retriever=setup.retriever,
        llm=llm,
        index_hash=setup.text_hash,
        lore=lore,
        agent=build_graph(
            setup.retriever,
            llm,
            max_retries=settings.retry_budget,
            multi_book=settings.multi_book,
            persona=PERSONA if settings.persona else None,
            lore=lore,
            lore_subject=settings.lore_subject,
            small_llm=small_llm,
            lesson=lesson,
            lesson_subject=settings.lore_subject,
            lesson_top_k=settings.lesson_top_k,
            lesson_min_score=settings.lesson_min_score,
        ),
        small_llm=small_llm,
        packs=packs,
        pack_store=pack_store,
        lesson=lesson,
    )
