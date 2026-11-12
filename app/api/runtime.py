"""Composition root: build the contract objects once, at app startup.

The API receives wired contracts and never builds a provider per request.
"""

import logging
from dataclasses import dataclass, field

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from app.agent import build_graph
from app.agent.memory import memory_saver
from app.agent.persona import PERSONAS
from app.config import Settings
from app.exam.bank import ExamBank
from app.grading import JudgeCache, default_judge_cache, judge_llm_from_bank
from app.knowledge import LoreStore, load_lore
from app.knowledge.lesson import LessonSelector
from app.knowledge.packs import PackStore, PackSummary, load_pack_store
from app.pipeline.retrieve import compose_retriever
from app.providers.contracts import Llm, Retriever
from app.providers.factory import make_embedder, make_llm, make_reranker
from app.storage.exam_store import ExamStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Runtime:
    """Wired contracts the API serves requests with."""

    retriever: Retriever
    llm: Llm
    agent: CompiledStateGraph | None = None
    stateless_agent: CompiledStateGraph | None = None
    index_hash: str = "unknown-index"
    small_llm: Llm | None = None
    lore: LoreStore | None = None
    packs: tuple[PackSummary, ...] = ()
    pack_store: PackStore | None = None
    lesson: LessonSelector | None = None
    exam_store: ExamStore | None = None
    # One judge per pinned model slug. Published banks may pin different judge
    # models, so grading selects the adapter from the attempt's own bank rather
    # than from OWL_EXAM_SUBJECT. `exam_judge` is an explicit single-judge
    # injection for tests and the browser stub, used only when the map is empty.
    exam_judges: dict[str, Llm] = field(default_factory=dict)
    exam_judge: Llm | None = None
    exam_cache: JudgeCache | None = None

    async def aclose(self) -> None:
        """Release provider clients and the serving store on shutdown."""
        components = [self.retriever, self.llm, self.small_llm, self.exam_judge]
        components.extend(self.exam_judges.values())
        seen: set[int] = set()
        for component in components:
            if component is None or id(component) in seen:
                continue
            seen.add(id(component))
            close = getattr(component, "aclose", None)
            if close is not None:
                await close()
        if self.exam_store is not None:
            self.exam_store.close()


def exam_judge_for(runtime: Runtime, bank: ExamBank) -> Llm | None:
    """The judge adapter pinned by this bank, never another subject's."""
    judge = runtime.exam_judges.get(bank.manifest.judge_model)
    if judge is None and not runtime.exam_judges:
        return runtime.exam_judge
    return judge


def lesson_available(
    settings: Settings, runtime: Runtime, subject: str | None = None
) -> bool:
    """One definition for the payload flag and the request gate.

    Lesson is available only when the feature is on, a selector exists, and the
    requested subject is one the selector can actually serve.
    """
    target = subject or settings.persona_subject
    return (
        settings.lesson_mode
        and runtime.lesson is not None
        and target in runtime.lesson.subjects()
    )


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
    exam_store: ExamStore | None = None
    exam_judges: dict[str, Llm] = {}
    exam_cache: JudgeCache | None = None
    if settings.exam_store_path.exists():
        try:
            exam_store = ExamStore(settings.exam_store_path)
            subjects = exam_store.published_subjects()
        except Exception as error:
            logger.warning("exam serving disabled: %s", error)
            if exam_store is not None:
                exam_store.close()
            exam_store = None
            subjects = []
        if exam_store is not None:
            manifests = []
            for subject in subjects:
                try:
                    manifest = exam_store.published_manifest(subject)
                except Exception as error:
                    # A malformed row disables that subject only; chat and the
                    # other banks keep serving.
                    logger.warning("exam bank unreadable for %s: %s", subject, error)
                    continue
                if manifest is not None:
                    manifests.append(manifest)
            if not manifests:
                logger.info("no published exam banks; exam routes stay empty")
            else:
                try:
                    exam_cache = default_judge_cache(config_settings=settings)
                except Exception as error:
                    logger.warning("exam grade cache disabled: %s", error)
                served: list[str] = []
                for manifest in manifests:
                    label = f"{manifest.subject} {manifest.version}"
                    if manifest.judge_model in exam_judges:
                        served.append(label)
                        continue
                    try:
                        bank = exam_store.bank(manifest.subject, manifest.version)
                        if bank is None:
                            logger.warning("exam bank unreadable: %s", label)
                            continue
                        exam_judges[manifest.judge_model] = judge_llm_from_bank(
                            bank, config_settings=settings
                        )
                    except Exception as error:
                        # One bad row must not take the whole app down: chat
                        # and the other banks keep serving.
                        logger.warning("exam bank unavailable: %s: %s", label, error)
                        continue
                    served.append(label)
                logger.info(
                    "exam banks served: %s; judge models: %s",
                    served or "none",
                    sorted(exam_judges) or "none",
                )
    else:
        logger.info(
            "exam bank absent at %s; exam routes stay empty",
            settings.exam_store_path,
        )
    def graph(checkpointer: MemorySaver | None) -> CompiledStateGraph:
        return build_graph(
            setup.retriever,
            llm,
            max_retries=settings.retry_budget,
            multi_book=settings.multi_book,
            personas=PERSONAS if settings.persona else None,
            default_subject=settings.persona_subject,
            lore=lore,
            small_llm=small_llm,
            lesson=lesson,
            lesson_top_k=settings.lesson_top_k,
            lesson_min_score=settings.lesson_min_score,
            lesson_fallback=settings.lesson_fallback,
            checkpointer=checkpointer,
            memory_window=settings.memory_window,
            memory_token_budget=settings.memory_token_budget,
        )

    agent = graph(memory_saver() if settings.memory_enabled else None)
    stateless_agent = graph(None) if settings.memory_enabled else agent
    return Runtime(
        retriever=setup.retriever,
        llm=llm,
        index_hash=setup.text_hash,
        lore=lore,
        agent=agent,
        stateless_agent=stateless_agent,
        small_llm=small_llm,
        packs=packs,
        pack_store=pack_store,
        lesson=lesson,
        exam_store=exam_store,
        exam_judges=exam_judges,
        exam_cache=exam_cache,
    )
