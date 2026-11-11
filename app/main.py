"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import random
import re
import secrets
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from app.agent import build_graph
from app.agent.persona import PERSONAS
from app.agent.router import classify
from app.api.cache import AnswerCache, cache_key
from app.api.limits import ChatLimiter, Decision, ExamAttemptLimiter
from app.api.runtime import Runtime, build_runtime, lesson_available
from app.api.schemas import (
    AskRequest,
    AskResponse,
    ExamGradeResponse,
    ExamPaper,
    GradeAttemptRequest,
    StreamRequest,
    SubjectsResponse,
)
from app.config import Settings, settings
from app.exam.attempts import AttemptRecord, AttemptSummary, AttemptView, sample_attempt
from app.exam.bank import MCQ_MARKS, SHORT_ANSWER_MARKS
from app.grading import AttemptAnswer, AttemptGrade, grade_attempt
from app.knowledge import LORE_SELECTION_VERSION
from app.knowledge.citations import check_authority, typed_from_legacy
from app.knowledge.taxonomy import SUBJECT_KEYS, SUBJECTS
from app.logging import configure_logging, get_request_id, set_request_id
from app.pipeline.generate import DEFAULT_TOP_K, SYSTEM_PROMPT, AskResult, ask
from app.providers.contracts import Llm, Retriever
from app.providers.errors import ProviderError
from app.storage.exam_store import ExamStore
from app.trace import TraceSink, current_tracer, end_trace, start_trace

logger = logging.getLogger(__name__)

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_SUBJECT_TITLES = dict(SUBJECTS)


def _typed_and_errors(
    result: AskResult, *, mode: str, needs_input: bool = False
) -> tuple[list[str], list[str]]:
    """The typed citations and the authority errors for one final answer."""
    typed = result.typed_citations or typed_from_legacy(
        result.citations, result.lore_citations, result.material_citations
    )
    errors = check_authority(
        typed,
        mode=mode,
        abstained=result.abstained,
        needs_input=needs_input or result.needs_input,
    )
    if errors:
        logger.warning(
            "citation authority errors mode=%s: %s",
            mode,
            "; ".join(errors),
        )
    return typed, errors


def _parse_paper_id(paper_id: str) -> tuple[str, str]:
    """Split `<subject>-<version>` against the known subject keys.

    Subject keys may themselves contain hyphens (`care-of-magical-creatures`),
    so match the longest known key rather than splitting on the first hyphen.
    """
    for subject in sorted(_SUBJECT_TITLES, key=len, reverse=True):
        prefix = f"{subject}-"
        if paper_id.startswith(prefix):
            version = paper_id[len(prefix) :]
            if version:
                return subject, version
    raise HTTPException(status_code=404, detail="paper not found")


def _client_ip(
    request: Request, trusted: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
) -> str:
    """The client address set by the trusted proxy, never the leftmost XFF.

    Proxy headers are honoured only when the peer is in a configured trusted
    CIDR. The Docker bridge gateway is included by default, because nginx reaches
    the container through it.
    """
    peer = request.client.host if request.client is not None else "unknown"
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return "unknown"
    if not any(address in network for network in trusted):
        return peer
    value = request.headers.get("x-real-ip")
    if value:
        try:
            return str(ipaddress.ip_address(value.strip()))
        except ValueError:
            pass
    return peer


def _sign(value: str, secret: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:32]


def _session_from_cookie(request: Request, secret: str) -> str | None:
    raw = request.cookies.get("owl_session")
    if not raw or "." not in raw:
        return None
    value, _, signature = raw.rpartition(".")
    if not value or not hmac.compare_digest(signature, _sign(value, secret)):
        return None
    return value


def create_app(app_settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    """Build the app; tests inject a Runtime so startup builds nothing real."""
    app_settings = app_settings or settings
    configure_logging(app_settings.log_level)
    if app_settings.multi_book and app_settings.persona:
        logger.warning(
            "OWL_MULTI_BOOK and OWL_PERSONA are both on; the multi-book path "
            "ignores the persona suffix"
        )
    trusted = [
        ipaddress.ip_network(item.strip())
        for item in app_settings.trusted_proxies.split(",")
        if item.strip()
    ]

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Built once, here, never per request.
        built = runtime or await build_runtime(app_settings)
        if built.agent is None:
            built = replace(
                built,
                agent=build_graph(
                    built.retriever,
                    built.llm,
                    max_retries=app_settings.retry_budget,
                    multi_book=app_settings.multi_book,
                    personas=PERSONAS if app_settings.persona else None,
                    default_subject=app_settings.persona_subject,
                    lore=built.lore,
                    small_llm=built.small_llm,
                    lesson=built.lesson,
                    lesson_top_k=app_settings.lesson_top_k,
                    lesson_min_score=app_settings.lesson_min_score,
                    lesson_fallback=app_settings.lesson_fallback,
                ),
            )
        app.state.runtime = built
        if not app_settings.session_secret:
            logger.warning(
                "OWL_SESSION_SECRET is unset; sessions reset on every restart"
            )
        app.state.session_secret = app_settings.session_secret or secrets.token_hex(32)
        app.state.limiter = ChatLimiter(app_settings)
        app.state.exam_limiter = ExamAttemptLimiter(app_settings)
        app.state.trace_sink = TraceSink(
            app_settings.trace_file, app_settings.trace_max_bytes
        )
        app.state.cache = AnswerCache(
            app_settings.chat_cache_entries, app_settings.chat_cache_ttl_s
        )
        try:
            yield
        finally:
            await app.state.runtime.aclose()

    app = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "service", "description": "Health and service discovery."},
            {
                "name": "chat",
                "description": "Grounded chat, practice, feedback and lesson answers.",
            },
            {
                "name": "subjects",
                "description": "Published subject packs and live flags.",
            },
            {"name": "exams", "description": "Served exam papers and attempts."},
            {
                "name": "attempts",
                "description": "Session-scoped attempt history, grading and deletion.",
            },
        ],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_origin_regex=app_settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        # Let a cross-origin chat page read the request id for support.
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        set_request_id(request_id)
        ip = _client_ip(request, trusted)
        secret = app.state.session_secret
        session = _session_from_cookie(request, secret)
        issue_cookie = session is None
        if session is None:
            session = secrets.token_hex(16)
        request.state.client_ip = ip
        request.state.session_id = session
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("failed %s %s", request.method, request.url.path)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        if issue_cookie:
            secure = request.url.scheme == "https" or (
                request.headers.get("x-forwarded-proto") == "https"
            )
            response.set_cookie(
                "owl_session",
                f"{session}.{_sign(session, secret)}",
                httponly=True,
                samesite="none" if secure else "lax",
                secure=secure,
                max_age=86_400,
            )
        # /health is polled; keep it out of the INFO stream.
        level = logging.DEBUG if request.url.path == "/health" else logging.INFO
        logger.log(
            level,
            "%s %s -> %d in %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    def get_retriever(request: Request) -> Retriever:
        return request.app.state.runtime.retriever

    def get_llm(request: Request) -> Llm:
        return request.app.state.runtime.llm

    def cache_scope(
        runtime: Runtime, model: str, persona_enabled: bool, subject: str
    ) -> str:
        """Everything besides the question that can change a cached answer."""
        card = PERSONAS.get(subject)
        persona_scope = (
            hashlib.sha256(card.answer_suffix().encode("utf-8")).hexdigest()[:8]
            if persona_enabled and card is not None
            else "off"
        )
        lesson_scope = (
            f"{runtime.pack_store.scope()}|{app_settings.lesson_top_k}|"
            f"{app_settings.lesson_min_score}|{app_settings.lesson_fallback}|"
            f"{subject}"
            if app_settings.lesson_mode and runtime.pack_store is not None
            else "off"
        )
        return "|".join(
            [
                runtime.index_hash,
                str(DEFAULT_TOP_K),
                app_settings.embedder_provider,
                app_settings.bedrock_embed_model,
                str(app_settings.bedrock_embed_dims),
                app_settings.rerank_provider,
                app_settings.rerank_model,
                str(app_settings.rerank_pool),
                str(app_settings.rerank_min_score),
                str(app_settings.retry_budget),
                str(app_settings.multi_book),
                persona_scope,
                lesson_scope,
                runtime.lore.version() if runtime.lore is not None else "none",
                LORE_SELECTION_VERSION,
                subject,
                model,
            ]
        )

    def limit_response(decision: Decision) -> JSONResponse:
        if decision.status == "degraded":
            return JSONResponse(
                status_code=503,
                content={
                    "error": "chat temporarily unavailable",
                    "reason": decision.reason,
                },
                headers={"Retry-After": str(decision.retry_after or 3600)},
            )
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate limited",
                "reason": decision.reason,
                "retry_after": decision.retry_after,
            },
            headers={"Retry-After": str(decision.retry_after or 60)},
        )

    def exam_limit_response(decision: Decision) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate limited",
                "reason": decision.reason,
                "retry_after": decision.retry_after,
            },
            headers={"Retry-After": str(decision.retry_after or 3600)},
        )

    def grade_response(
        record: AttemptRecord, grade: AttemptGrade
    ) -> ExamGradeResponse:
        return ExamGradeResponse(
            attempt_id=record.attempt_id,
            paper_id=record.paper_id,
            total=grade.total,
            max_marks=grade.max_marks,
            band=grade.band,
            needs_review=grade.needs_review,
            graded_at=grade.graded_at,
            questions=list(grade.questions),
        )

    def owned_attempt(
        store: ExamStore, attempt_id: str, session_id: str
    ) -> AttemptRecord:
        """An attempt is visible only to the session that started it."""
        record = store.attempt(attempt_id)
        if record is None or record.session_id != session_id:
            raise HTTPException(status_code=404, detail="attempt not found")
        return record

    def record_usage(
        request: Request,
        *,
        intent: str,
        model: str,
        cache_hit: bool,
        question: str,
        result: AskResult,
        latency_ms: float,
        student: str = "",
        subject: str = "",
    ) -> None:
        limiter: ChatLimiter = app.state.limiter
        # A scripted meta or personal reply makes no model call; it must not
        # charge the daily budget as if it did.
        scripted = result.model_calls == 0 and result.attempts == 0
        attempts = 0 if scripted else max(1, result.model_calls or result.attempts)
        card = PERSONAS.get(subject or app_settings.persona_subject)
        persona_chars = (
            len(card.answer_suffix())
            if app_settings.persona
            and card is not None
            and intent == "answer"
            and not app_settings.multi_book
            else 0
        )
        per_draft = (
            result.prompt_chars
            if result.prompt_chars
            else (
                len(SYSTEM_PROMPT)
                + persona_chars
                + len(question)
                + len(student)
                + result.lore_chars
                + sum(len(chunk.text) for chunk in result.chunks)
            )
        )
        input_tokens = (
            0 if cache_hit or scripted else max(1, attempts * per_draft // 4)
        )
        output_chars = attempts * (200 if result.abstained else len(result.answer))
        output_tokens = 0 if cache_hit or scripted else max(1, output_chars // 4)
        small_model = getattr(getattr(request.app.state.runtime, "small_llm", None), "name", None)
        cost = (
            0.0
            if cache_hit or scripted
            else limiter.cost(input_tokens, output_tokens, small=model == small_model)
        )
        if not cache_hit and not scripted:
            limiter.record(input_tokens, output_tokens)
        logger.info(
            "chat usage session=%s intent=%s model=%s cache=%s in_tokens=%d "
            "out_tokens=%d cost_usd=%.6f latency_ms=%.0f",
            request.state.session_id,
            intent,
            model,
            cache_hit,
            input_tokens,
            output_tokens,
            cost,
            latency_ms,
        )

    @app.get("/health", tags=["service"], summary="Liveness probe")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/v1/subjects",
        response_model=SubjectsResponse,
        tags=["subjects"],
        summary="Published subject packs and live flags",
    )
    def subjects(request: Request) -> SubjectsResponse:
        """Published packs only; drafts stay invisible to the frontend."""
        runtime = request.app.state.runtime
        lesson = lesson_available(app_settings, runtime)
        lesson_subjects = (
            sorted(runtime.lesson.subjects())
            if app_settings.lesson_mode and runtime.lesson is not None
            else []
        )
        return SubjectsResponse(
            subjects=list(runtime.packs),
            lesson=lesson,
            lesson_subject=app_settings.persona_subject if lesson else "",
            lesson_subjects=lesson_subjects,
            lesson_fallback=app_settings.lesson_fallback,
            persona=app_settings.persona,
            persona_subject=app_settings.persona_subject if app_settings.persona else "",
            persona_subjects=(
                sorted(PERSONAS) if app_settings.persona else []
            ),
        )

    @app.get("/", tags=["service"], summary="Service descriptor")
    def service_root() -> dict[str, str]:
        """A JSON descriptor, not a chat page.

        The academy frontend is the Cloudflare Pages build. The API host used
        to serve a single-file chat page; it was removed so the API origin
        cannot be used as a second chat surface.
        """
        return {
            "service": "owl-online-api",
            "status": "ok",
            "health": "/health",
            "subjects": "/v1/subjects",
        }

    def persona_enabled_for(subject: str) -> bool:
        """Every registered subject gets its own live card."""
        return app_settings.persona and (
            subject or app_settings.persona_subject
        ) in PERSONAS

    @app.post(
        "/v1/chat",
        response_model=AskResponse,
        tags=["chat"],
        summary="Ask one grounded question",
    )
    @app.post(
        "/ask",
        response_model=AskResponse,
        tags=["chat"],
        summary="Ask one grounded question (deprecated alias)",
        deprecated=True,
    )
    async def ask_endpoint(
        body: AskRequest,
        request: Request,
        response: Response,
        retriever: Annotated[Retriever, Depends(get_retriever)],
        llm: Annotated[Llm, Depends(get_llm)],
    ) -> AskResponse | JSONResponse:
        if request.url.path == "/ask":
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = '</v1/chat>; rel="successor-version"'
        session = request.state.session_id
        limiter: ChatLimiter = app.state.limiter
        runtime = request.app.state.runtime
        model = getattr(llm, "name", "?")
        subject = body.subject or app_settings.persona_subject
        if body.subject and body.subject not in SUBJECT_KEYS:
            raise HTTPException(status_code=422, detail="unknown subject")
        persona_enabled = persona_enabled_for(subject)
        persona = PERSONAS.get(subject) if persona_enabled else None
        key = cache_key(
            body.question,
            cache_scope(runtime, model, persona_enabled, subject),
            model,
        )
        cached = app.state.cache.get(key)
        decision = limiter.admit(
            session, request.state.client_ip, cache_hit=cached is not None
        )
        if not decision.allowed:
            return limit_response(decision)
        stage = {"name": "retrieve"}

        def mark(name: str) -> None:
            stage["name"] = name

        trace_token = start_trace(get_request_id(), app.state.trace_sink)
        try:
            if cached is not None:
                tracer = current_tracer()
                if tracer is not None:
                    tracer.emit("cache", hit=True, intent="answer")
                record_usage(
                    request,
                    intent="answer",
                    model=model,
                    cache_hit=True,
                    question=body.question,
                    result=cached,
                    latency_ms=0.0,
                    subject=subject,
                )
                typed, errors = _typed_and_errors(cached, mode="answer")
                return AskResponse(
                    answer=cached.answer,
                    citations=cached.citations,
                    abstained=cached.abstained,
                    lore_citations=cached.lore_citations,
                    material_citations=cached.material_citations,
                    typed_citations=typed,
                    citation_errors=errors,
                )
            start = time.perf_counter()
            try:
                async with asyncio.timeout(app_settings.ask_timeout_s):
                    result = await ask(
                        body.question,
                        retriever=retriever,
                        llm=llm,
                        max_retries=app_settings.retry_budget,
                        multi_book=app_settings.multi_book,
                        persona_suffix=(
                            persona.answer_suffix() if persona is not None else None
                        ),
                        lore=runtime.lore,
                        subject=subject,
                        on_stage=mark,
                    )
                    if persona is not None and result.abstained:
                        result = replace(
                            result, answer=persona.abstain_response()
                        )
            except TimeoutError:
                request_id = get_request_id()
                logger.warning(
                    "deadline exceeded in %s after %.0fs (request %s)",
                    stage["name"],
                    app_settings.ask_timeout_s,
                    request_id,
                )
                return JSONResponse(
                    status_code=504,
                    content={"error": "deadline exceeded", "request_id": request_id},
                )
            except ProviderError as exc:
                # Normalized provider failure: a clean 502, never a stack trace.
                raise HTTPException(
                    status_code=502, detail="model provider unavailable"
                ) from exc
            if not result.abstained:
                app.state.cache.put(key, result)
            record_usage(
                request,
                intent="answer",
                model=model,
                cache_hit=False,
                question=body.question,
                result=result,
                latency_ms=(time.perf_counter() - start) * 1000,
                subject=subject,
            )
            typed, errors = _typed_and_errors(result, mode="answer")
            return AskResponse(
                answer=result.answer,
                citations=result.citations,
                abstained=result.abstained,
                lore_citations=result.lore_citations,
                material_citations=result.material_citations,
                typed_citations=typed,
                citation_errors=errors,
            )
        finally:
            limiter.release(decision.token)
            try:
                end_trace(trace_token)
            except ValueError:
                pass

    @app.post(
        "/v1/chat/stream",
        response_model=None,
        tags=["chat"],
        summary="Stream a chat answer over SSE",
    )
    @app.post(
        "/ask/stream",
        response_model=None,
        tags=["chat"],
        summary="Stream a chat answer over SSE (deprecated alias)",
        deprecated=True,
    )
    async def ask_stream_endpoint(
        body: StreamRequest, request: Request
    ) -> EventSourceResponse | JSONResponse:
        runtime = request.app.state.runtime
        agent = runtime.agent
        if agent is None:
            raise RuntimeError("agent graph was not built")
        subject = body.subject or app_settings.persona_subject
        if body.subject and body.subject not in SUBJECT_KEYS:
            raise HTTPException(status_code=422, detail="unknown subject")
        session = request.state.session_id
        limiter: ChatLimiter = app.state.limiter
        llm = runtime.llm
        model = getattr(llm, "name", "?")
        persona_enabled = persona_enabled_for(subject)
        intent = classify(
            body.question,
            requested_mode=body.mode,
            student_answer=body.student_answer,
            persona=persona_enabled,
            subject=subject,
        )
        if (
            body.mode == "lesson"
            and intent == "lesson"
            and not lesson_available(app_settings, runtime, subject)
        ):
            raise HTTPException(status_code=400, detail="lesson mode is not enabled")
        # Only corpus-only answers are shared; feedback is personalised,
        # practice is meant to vary, and meta/personal are scripted.
        key = (
            cache_key(
                body.question,
                cache_scope(runtime, model, persona_enabled, subject),
                model,
            )
            if intent == "answer"
            else None
        )
        cached = app.state.cache.get(key) if key else None
        decision = limiter.admit(
            session, request.state.client_ip, cache_hit=cached is not None
        )
        if not decision.allowed:
            return limit_response(decision)
        initial = {
            "question": body.question,
            "requested_mode": body.mode,
            "student_answer": body.student_answer,
            "subject": subject,
            "persona_enabled": persona_enabled,
            "top_k": DEFAULT_TOP_K,
        }
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        if request.url.path == "/ask/stream":
            headers["Deprecation"] = "true"
            headers["Link"] = '</v1/chat/stream>; rel="successor-version"'

        if cached is not None:

            async def cached_events() -> AsyncIterator[dict[str, str]]:
                token = start_trace(get_request_id(), app.state.trace_sink)
                try:
                    tracer = current_tracer()
                    if tracer is not None:
                        tracer.emit("cache", hit=True, intent="answer")
                    yield {
                        "event": "mode",
                        "data": json.dumps({"mode": "answer"}, ensure_ascii=False),
                    }
                    if cached.abstain_reason != "no_evidence":
                        yield {
                            "event": "token",
                            "data": json.dumps(
                                {"text": cached.answer}, ensure_ascii=False
                            ),
                        }
                    record_usage(
                        request,
                        intent="answer",
                        model=model,
                        cache_hit=True,
                        question=body.question,
                        result=cached,
                        latency_ms=0.0,
                        subject=subject,
                    )
                    if cached.abstained:
                        yield {"event": "reset", "data": json.dumps({})}
                    typed, errors = _typed_and_errors(cached, mode="answer")
                    yield {
                        "event": "final",
                        "data": json.dumps(
                            {
                                "answer": cached.answer,
                                "citations": cached.citations,
                                "lore_citations": cached.lore_citations,
                                "material_citations": cached.material_citations,
                                "typed_citations": typed,
                                "citation_errors": errors,
                                "scope": cached.scope,
                                "abstained": cached.abstained,
                                "needs_input": False,
                                "attempts": cached.attempts,
                                "mode": "answer",
                            },
                            ensure_ascii=False,
                        ),
                    }
                finally:
                    limiter.release(decision.token)
                    try:
                        end_trace(token)
                    except ValueError:
                        pass

            async def release_cached() -> None:
                limiter.release(decision.token)

            return EventSourceResponse(
                cached_events(),
                headers=headers,
                background=BackgroundTask(release_cached),
            )

        async def events() -> AsyncIterator[dict[str, str]]:
            final: dict[str, object] = dict(initial)
            start = time.perf_counter()
            try:
                async for mode, chunk in agent.astream(
                    initial, stream_mode=["custom", "updates"]
                ):
                    if mode == "custom":
                        payload = dict(chunk)
                        event = str(payload.pop("type", "message"))
                        yield {
                            "event": event,
                            "data": json.dumps(payload, ensure_ascii=False),
                        }
                    elif mode == "updates":
                        for node, update in chunk.items():
                            final.update(update)
                            if node == "router":
                                yield {
                                    "event": "mode",
                                    "data": json.dumps(
                                        {"mode": update.get("mode")},
                                        ensure_ascii=False,
                                    ),
                                }
            except ProviderError:
                logger.exception("streaming provider failure")
                # error is terminal; clear any draft the client is showing.
                yield {"event": "reset", "data": json.dumps({})}
                yield {
                    "event": "error",
                    "data": json.dumps({"detail": "model provider unavailable"}),
                }
                return
            except Exception:
                logger.exception("streaming failure")
                yield {"event": "reset", "data": json.dumps({})}
                yield {
                    "event": "error",
                    "data": json.dumps({"detail": "internal error"}),
                }
                return
            # Tokens are a draft. The final event is authoritative: an abstained
            # answer tells the client to replace the draft, and reset does it
            # explicitly before the final payload.
            result = AskResult(
                answer=str(final.get("answer", "")),
                citations=list(final.get("citations", [])),
                lore_citations=list(final.get("lore_citations", [])),
                material_citations=list(final.get("material_citations", [])),
                typed_citations=list(final.get("typed_citations", [])),
                needs_input=bool(final.get("needs_input", False)),
                scope=final.get("scope"),
                prompt_chars=int(final.get("prompt_chars") or 0),
                lore_chars=int(final.get("lore_chars") or 0),
                abstained=bool(final.get("abstained", False)),
                chunks=list(final.get("chunks", [])),
                attempts=int(final.get("attempts", 1)),
                model_calls=int(final.get("model_calls") or 0),
                abstain_reason=final.get("abstain_reason"),  # type: ignore[arg-type]
            )
            if key is not None and not result.abstained:
                app.state.cache.put(key, result)
            used_model = str(final.get("llm_model") or model)
            record_usage(
                request,
                intent=str(final.get("mode", intent)),
                model=used_model,
                cache_hit=False,
                question=body.question,
                result=result,
                latency_ms=(time.perf_counter() - start) * 1000,
                student=body.student_answer or "",
                subject=subject,
            )
            if final.get("abstained"):
                yield {"event": "reset", "data": json.dumps({})}
            mode = str(final.get("mode", intent))
            typed, errors = _typed_and_errors(
                result, mode=mode, needs_input=bool(final.get("needs_input", False))
            )
            yield {
                "event": "final",
                "data": json.dumps(
                    {
                        "answer": final.get("answer", ""),
                        "citations": final.get("citations", []),
                        "lore_citations": final.get("lore_citations", []),
                        "material_citations": final.get("material_citations", []),
                        "typed_citations": typed,
                        "citation_errors": errors,
                        "scope": final.get("scope"),
                        "abstained": final.get("abstained", False),
                        "needs_input": final.get("needs_input", False),
                        "attempts": final.get("attempts", 1),
                        "mode": mode,
                    },
                    ensure_ascii=False,
                ),
            }


        async def guarded() -> AsyncIterator[dict[str, str]]:
            token = start_trace(get_request_id(), app.state.trace_sink)
            try:
                async for event in events():
                    yield event
            finally:
                limiter.release(decision.token)
                try:
                    end_trace(token)
                except ValueError:
                    pass

        async def release_lease() -> None:
            limiter.release(decision.token)

        return EventSourceResponse(
            guarded(),
            headers=headers,
            background=BackgroundTask(release_lease),
        )

    @app.get(
        "/v1/exams",
        response_model=list[ExamPaper],
        tags=["exams"],
        summary="Published paper descriptors",
    )
    def exams(
        request: Request,
        subject: str | None = None,
        version: str | None = None,
    ) -> list[ExamPaper]:
        """Published paper descriptors; questions are sampled per attempt."""
        store = request.app.state.runtime.exam_store
        if store is None:
            return []
        subject = subject or app_settings.exam_subject
        manifest = store.published_manifest(subject, version)
        if manifest is None:
            return []
        mcq_count = app_settings.exam_mcq_count
        short_count = app_settings.exam_short_count
        if (
            manifest.mcq_count < mcq_count
            or manifest.short_answer_count < short_count
        ):
            return []
        return [
            ExamPaper(
                paper_id=f"{manifest.subject}-{manifest.version}",
                subject=manifest.subject,
                version=manifest.version,
                title=_SUBJECT_TITLES.get(manifest.subject, manifest.subject),
                question_count=mcq_count + short_count,
                mcq_count=mcq_count,
                short_answer_count=short_count,
                marks=mcq_count * MCQ_MARKS + short_count * SHORT_ANSWER_MARKS,
                duration_minutes=app_settings.exam_duration_minutes,
            )
        ]

    @app.post(
        "/v1/exams/{paper_id}/attempts",
        response_model=AttemptView,
        status_code=201,
        tags=["exams"],
        summary="Sample and persist a paper attempt",
    )
    def start_attempt(
        paper_id: str, request: Request
    ) -> AttemptView | JSONResponse:
        """Sample and persist one attempt; the response never contains the key."""
        store = request.app.state.runtime.exam_store
        if store is None:
            raise HTTPException(status_code=503, detail="exam bank unavailable")
        subject, version = _parse_paper_id(paper_id)
        bank = store.bank(subject, version)
        if bank is None:
            raise HTTPException(status_code=404, detail="paper not found")
        limiter: ExamAttemptLimiter = app.state.exam_limiter
        decision = limiter.admit(
            request.state.session_id, client_ip=_client_ip(request, trusted)
        )
        if not decision.allowed:
            return exam_limit_response(decision)
        try:
            record = sample_attempt(
                bank,
                attempt_id=secrets.token_urlsafe(24),
                paper_id=paper_id,
                created_at=datetime.now(UTC)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                mcq_count=app_settings.exam_mcq_count,
                short_count=app_settings.exam_short_count,
                session_id=request.state.session_id,
                rng=random.Random(secrets.randbits(64)),
            )
            store.create_attempt(record)
        except ValueError as error:
            raise HTTPException(
                status_code=503, detail="exam bank cannot serve this paper"
            ) from error
        return record.view()

    @app.get(
        "/v1/attempts",
        response_model=list[AttemptSummary],
        tags=["attempts"],
        summary="Graded attempts for the current session",
    )
    def list_attempts(
        request: Request,
        subject: str | None = None,
        limit: int = Query(default=50, ge=1, le=50),
    ) -> list[AttemptSummary]:
        """Graded attempts for the current session, newest first."""
        store = request.app.state.runtime.exam_store
        if store is None:
            raise HTTPException(status_code=503, detail="exam bank unavailable")
        return store.list_attempts(
            session_id=request.state.session_id,
            subject=subject or app_settings.exam_subject,
            limit=limit,
        )

    @app.delete(
        "/v1/attempts",
        tags=["attempts"],
        summary="Delete the current session attempts",
    )
    def delete_attempts(request: Request) -> dict[str, int]:
        """Delete the current session's attempts (the anonymous delete path)."""
        store = request.app.state.runtime.exam_store
        if store is None:
            raise HTTPException(status_code=503, detail="exam bank unavailable")
        return {"deleted": store.delete_attempts(request.state.session_id)}

    @app.get(
        "/v1/attempts/{attempt_id}",
        response_model=AttemptView,
        tags=["attempts"],
        summary="Persisted pre-submission attempt",
    )
    def get_attempt(attempt_id: str, request: Request) -> AttemptView:
        """The same persisted view on a reload; options are not reshuffled."""
        store = request.app.state.runtime.exam_store
        if store is None:
            raise HTTPException(status_code=503, detail="exam bank unavailable")
        record = owned_attempt(store, attempt_id, request.state.session_id)
        return record.view()

    @app.post(
        "/v1/attempts/{attempt_id}/grade",
        response_model=ExamGradeResponse,
        tags=["attempts"],
        summary="Grade an attempt",
    )
    async def grade_attempt_endpoint(
        attempt_id: str,
        body: GradeAttemptRequest,
        request: Request,
    ) -> ExamGradeResponse:
        """Score the attempt: deterministic MCQ and one short-answer judge call."""
        runtime = request.app.state.runtime
        store = runtime.exam_store
        if store is None:
            raise HTTPException(status_code=503, detail="exam bank unavailable")
        record = owned_attempt(store, attempt_id, request.state.session_id)
        if record.grade is not None:
            return grade_response(record, record.grade)
        bank = store.bank(record.subject, record.bank_version)
        if bank is None:
            raise HTTPException(status_code=503, detail="paper unavailable")
        judge = runtime.exam_judge
        if judge is None:
            raise HTTPException(status_code=503, detail="grading unavailable")
        by_id = {question.item_id: question for question in record.questions}
        answers: list[AttemptAnswer] = []
        seen: set[str] = set()
        for answer in body.answers:
            if answer.item_id not in by_id:
                raise HTTPException(
                    status_code=400,
                    detail="answer for an item outside the attempt",
                )
            if answer.item_id in seen:
                raise HTTPException(status_code=400, detail="duplicate answer")
            seen.add(answer.item_id)
            question = by_id[answer.item_id]
            if question.kind == "mcq":
                if answer.option_id is None:
                    raise HTTPException(
                        status_code=400, detail="MCQ answers use option_id"
                    )
                served = {option.option_id for option in question.options}
                if answer.option_id not in served:
                    raise HTTPException(
                        status_code=400,
                        detail="option id is not one of the served options",
                    )
                answers.append(
                    AttemptAnswer(item_id=answer.item_id, option_id=answer.option_id)
                )
            else:
                if answer.option_id is not None:
                    raise HTTPException(
                        status_code=400,
                        detail="short answers use answer_text",
                    )
                answers.append(
                    AttemptAnswer(
                        item_id=answer.item_id,
                        answer_text=answer.answer_text or "",
                    )
                )
        try:
            grade = await grade_attempt(
                bank,
                list(record.item_ids),
                answers,
                llm=judge,
                cache=runtime.exam_cache,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=503, detail="grading unavailable"
            ) from error
        except ProviderError as error:
            raise HTTPException(
                status_code=502, detail="model provider unavailable"
            ) from error
        store.save_grade(attempt_id, grade, answers)
        return grade_response(record, grade)

    return app


app = create_app()
