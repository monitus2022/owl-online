"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.background import BackgroundTask

from app.agent import build_graph
from app.agent.persona import PERSONA
from app.agent.router import classify
from app.api.cache import AnswerCache, cache_key
from app.api.limits import ChatLimiter, Decision
from app.api.runtime import Runtime, build_runtime
from app.api.schemas import AskRequest, AskResponse, StreamRequest
from app.config import Settings, settings
from app.logging import configure_logging, get_request_id, set_request_id
from app.pipeline.generate import DEFAULT_TOP_K, SYSTEM_PROMPT, AskResult, ask
from app.providers.contracts import Llm, Retriever
from app.providers.errors import ProviderError
from app.trace import TraceSink, current_tracer, end_trace, start_trace

logger = logging.getLogger(__name__)

_INDEX_HTML = Path(__file__).parent / "api" / "static" / "index.html"
_INDEX_HTML_TEXT = _INDEX_HTML.read_text(encoding="utf-8")
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


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
                    persona=PERSONA if app_settings.persona else None,
                    small_llm=built.small_llm,
                ),
            )
        app.state.runtime = built
        if not app_settings.session_secret:
            logger.warning(
                "OWL_SESSION_SECRET is unset; sessions reset on every restart"
            )
        app.state.session_secret = app_settings.session_secret or secrets.token_hex(32)
        app.state.limiter = ChatLimiter(app_settings)
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

    app = FastAPI(title=app_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_origin_regex=app_settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
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

    def cache_scope(runtime: Runtime, model: str) -> str:
        """Everything besides the question that can change a cached answer."""
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
                str(app_settings.persona),
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
    ) -> None:
        limiter: ChatLimiter = app.state.limiter
        attempts = max(1, result.model_calls or result.attempts)
        per_draft = len(SYSTEM_PROMPT) + len(question) + len(student) + sum(
            len(chunk.text) for chunk in result.chunks
        )
        input_tokens = 0 if cache_hit else max(1, attempts * per_draft // 4)
        output_chars = attempts * (200 if result.abstained else len(result.answer))
        output_tokens = 0 if cache_hit else max(1, output_chars // 4)
        small_model = getattr(getattr(request.app.state.runtime, "small_llm", None), "name", None)
        cost = (
            0.0
            if cache_hit
            else limiter.cost(input_tokens, output_tokens, small=model == small_model)
        )
        if not cache_hit:
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def chat_page() -> HTMLResponse:
        return HTMLResponse(_INDEX_HTML_TEXT)

    @app.post("/ask", response_model=AskResponse)
    async def ask_endpoint(
        body: AskRequest,
        request: Request,
        retriever: Annotated[Retriever, Depends(get_retriever)],
        llm: Annotated[Llm, Depends(get_llm)],
    ) -> AskResponse | JSONResponse:
        session = request.state.session_id
        limiter: ChatLimiter = app.state.limiter
        runtime = request.app.state.runtime
        model = getattr(llm, "name", "?")
        key = cache_key(body.question, cache_scope(runtime, model), model)
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
                )
                return AskResponse(
                    answer=cached.answer,
                    citations=cached.citations,
                    abstained=cached.abstained,
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
                            PERSONA.answer_suffix() if app_settings.persona else None
                        ),
                        on_stage=mark,
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
            )
            return AskResponse(
                answer=result.answer,
                citations=result.citations,
                abstained=result.abstained,
            )
        finally:
            limiter.release(decision.token)
            try:
                end_trace(trace_token)
            except ValueError:
                pass

    @app.post("/ask/stream", response_model=None)
    async def ask_stream_endpoint(
        body: StreamRequest, request: Request
    ) -> EventSourceResponse | JSONResponse:
        runtime = request.app.state.runtime
        agent = runtime.agent
        if agent is None:
            raise RuntimeError("agent graph was not built")
        session = request.state.session_id
        limiter: ChatLimiter = app.state.limiter
        llm = runtime.llm
        model = getattr(llm, "name", "?")
        intent = classify(
            body.question,
            requested_mode=body.mode,
            student_answer=body.student_answer,
        )
        # Only corpus-only answers are shared; feedback is personalised and
        # practice is meant to vary.
        key = (
            cache_key(body.question, cache_scope(runtime, model), model)
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
            "top_k": DEFAULT_TOP_K,
        }
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

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
                    )
                    if cached.abstained:
                        yield {"event": "reset", "data": json.dumps({})}
                    yield {
                        "event": "final",
                        "data": json.dumps(
                            {
                                "answer": cached.answer,
                                "citations": cached.citations,
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
            )
            if final.get("abstained"):
                yield {"event": "reset", "data": json.dumps({})}
            yield {
                "event": "final",
                "data": json.dumps(
                    {
                        "answer": final.get("answer", ""),
                        "citations": final.get("citations", []),
                        "abstained": final.get("abstained", False),
                        "needs_input": final.get("needs_input", False),
                        "attempts": final.get("attempts", 1),
                        "mode": final.get("mode", "answer"),
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

    return app


app = create_app()
