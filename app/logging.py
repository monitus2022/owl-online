"""Application logging: one formatter, a level from settings, a per-request id.

Modules use logging.getLogger(__name__). The request id travels in a ContextVar
so every line from one request can be tied together, and the API echoes it as
X-Request-ID. configure_logging() is called once from create_app().
"""

import logging
from contextvars import ContextVar

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="-")
_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"


class _OwlHandler(logging.StreamHandler):
    """Tagged so configure_logging replaces only its own handler, not pytest's."""


class _RequestIdFilter(logging.Filter):
    """Attach the current request id to every record on this handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _REQUEST_ID.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Install one stream handler on the root logger. Safe to call repeatedly."""
    root = logging.getLogger()
    for existing in list(root.handlers):
        if isinstance(existing, _OwlHandler):
            root.removeHandler(existing)

    handler = _OwlHandler()
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)
    root.setLevel(level.upper())

    # The API middleware logs the access line (with the request id and timing),
    # so uvicorn's own access line would be a duplicate. The model SDKs' httpx
    # request lines are noise next to the providers' own DEBUG timings.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def set_request_id(value: str) -> None:
    """Bind the request id for the current async context."""
    _REQUEST_ID.set(value)


def get_request_id() -> str:
    """The current request id, or '-' outside a request."""
    return _REQUEST_ID.get()
