"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""

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

from app.api.runtime import Runtime, build_runtime
from app.api.schemas import AskRequest, AskResponse
from app.config import Settings, settings
from app.logging import configure_logging, set_request_id
from app.pipeline.generate import ask
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

    return app


app = create_app()
