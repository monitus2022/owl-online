"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from app.agent import build_graph
from app.api.runtime import Runtime, build_runtime
from app.api.schemas import AskRequest, AskResponse, StreamRequest
from app.config import Settings, settings
from app.logging import configure_logging, set_request_id
from app.pipeline.generate import DEFAULT_TOP_K, ask
from app.providers.contracts import Llm, Retriever
from app.providers.errors import ProviderError

logger = logging.getLogger(__name__)

_INDEX_HTML = Path(__file__).parent / "api" / "static" / "index.html"
_INDEX_HTML_TEXT = _INDEX_HTML.read_text(encoding="utf-8")


def create_app(app_settings: Settings | None = None, runtime: Runtime | None = None) -> FastAPI:
    """Build the app; tests inject a Runtime so startup builds nothing real."""
    app_settings = app_settings or settings
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Built once, here, never per request.
        app.state.runtime = runtime or await build_runtime(app_settings)
        try:
            yield
        finally:
            await app.state.runtime.aclose()

    app = FastAPI(title=app_settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origin_list,
        allow_origin_regex=app_settings.cors_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        # Let a cross-origin chat page read the request id for support.
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def log_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        set_request_id(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("failed %s %s", request.method, request.url.path)
            raise
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def chat_page() -> HTMLResponse:
        return HTMLResponse(_INDEX_HTML_TEXT)

    @app.post("/ask", response_model=AskResponse)
    async def ask_endpoint(
        body: AskRequest,
        retriever: Annotated[Retriever, Depends(get_retriever)],
        llm: Annotated[Llm, Depends(get_llm)],
    ) -> AskResponse:
        try:
            result = await ask(body.question, retriever=retriever, llm=llm)
        except ProviderError as exc:
            # Normalized provider failure: a clean 502, never a stack trace.
            raise HTTPException(status_code=502, detail="model provider unavailable") from exc
        return AskResponse(
            answer=result.answer,
            citations=result.citations,
            abstained=result.abstained,
        )

    @app.post("/ask/stream")
    async def ask_stream_endpoint(
        body: StreamRequest, request: Request
    ) -> EventSourceResponse:
        runtime = request.app.state.runtime
        agent = runtime.agent or build_graph(runtime.retriever, runtime.llm)
        initial = {
            "question": body.question,
            "requested_mode": body.mode,
            "student_answer": body.student_answer,
            "top_k": DEFAULT_TOP_K,
        }

        async def events() -> AsyncIterator[dict[str, str]]:
            final: dict[str, object] = dict(initial)
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
                yield {
                    "event": "error",
                    "data": json.dumps({"detail": "model provider unavailable"}),
                }
                return
            except Exception:
                logger.exception("streaming failure")
                yield {
                    "event": "error",
                    "data": json.dumps({"detail": "internal error"}),
                }
                return

            # Tokens are a draft. The final event is authoritative: an abstained
            # answer tells the client to replace the draft, and reset does it
            # explicitly before the final payload.
            if final.get("abstained"):
                yield {"event": "reset", "data": json.dumps({})}
            yield {
                "event": "final",
                "data": json.dumps(
                    {
                        "answer": final.get("answer", ""),
                        "citations": final.get("citations", []),
                        "abstained": final.get("abstained", False),
                        "mode": final.get("mode", "answer"),
                    },
                    ensure_ascii=False,
                ),
            }

        return EventSourceResponse(
            events(),
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
