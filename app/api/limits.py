"""In-process chat limits, usage accounting and the daily spend guard.

One API process on one host, so memory is enough; a restart resets the windows,
which is acceptable for anonymous caps. Chat only: exam routes will use their
own dependency when they exist, so degrading chat never takes them down.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.config import Settings

logger = logging.getLogger(__name__)

DecisionStatus = Literal["ok", "rate_limited", "degraded"]


def session_id_for(ip: str, user_agent: str) -> str:
    """Stable anonymous session from the client fingerprint."""
    material = f"{ip}\n{user_agent}".encode()
    return hashlib.sha256(material).hexdigest()[:16]


@dataclass(frozen=True)
class Decision:
    """Admission outcome for one chat request."""

    status: DecisionStatus
    reason: str | None = None
    retry_after: int | None = None

    @property
    def allowed(self) -> bool:
        return self.status == "ok"


@dataclass
class _Window:
    minute_start: float = 0.0
    minute_count: int = 0
    day: str = ""
    day_count: int = 0


class ChatLimiter:
    """Per-session and per-IP counters plus a daily token budget."""

    def __init__(
        self,
        settings: Settings,
        *,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], str] | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._today = today or (lambda: datetime.now(UTC).strftime("%Y-%m-%d"))
        self._windows: dict[str, _Window] = {}
        self._ip_windows: dict[str, _Window] = {}
        self._active: dict[str, int] = {}
        self._tokens_day = ""
        self._tokens = 0
        self._alerts: set[int] = set()

    def admit(self, session: str, ip: str) -> Decision:
        """Check the limits and, when allowed, count the request."""
        now = self._clock()
        day = self._today()
        self._roll_day(day)
        window = self._windows.setdefault(session, _Window())
        ip_window = self._ip_windows.setdefault(ip, _Window())
        self._roll_window(window, ip_window, now, day)

        if window.minute_count >= self._settings.chat_per_minute:
            retry = max(1, math.ceil(60 - (now - window.minute_start)))
            return Decision("rate_limited", "minute", retry)
        if window.day_count >= self._settings.chat_per_day:
            return Decision("rate_limited", "day", 3600)
        if ip_window.day_count >= self._settings.chat_ip_per_day:
            return Decision("rate_limited", "ip_day", 3600)
        if self._tokens >= self._settings.chat_daily_token_budget:
            return Decision("degraded", "budget", 3600)
        if self._active.get(session, 0) >= self._settings.chat_concurrent:
            return Decision("rate_limited", "concurrent", 1)

        window.minute_count += 1
        window.day_count += 1
        ip_window.day_count += 1
        self._active[session] = self._active.get(session, 0) + 1
        return Decision("ok")

    def release(self, session: str) -> None:
        self._active[session] = max(0, self._active.get(session, 1) - 1)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        prices = self._settings
        return (
            input_tokens * prices.chat_input_price_per_mtok
            + output_tokens * prices.chat_output_price_per_mtok
        ) / 1_000_000

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Account one answered request against the daily budget."""
        day = self._today()
        self._roll_day(day)
        self._tokens += max(0, input_tokens) + max(0, output_tokens)
        budget = self._settings.chat_daily_token_budget
        for percent in (50, 80):
            if self._tokens >= budget * percent / 100 and percent not in self._alerts:
                self._alerts.add(percent)
                logger.warning(
                    "chat budget at %d%% (%d/%d tokens)", percent, self._tokens, budget
                )

    @property
    def tokens_used(self) -> int:
        return self._tokens

    def _roll_day(self, day: str) -> None:
        if self._tokens_day == day:
            return
        self._tokens_day = day
        self._tokens = 0
        self._alerts.clear()

    def _roll_window(
        self, window: _Window, ip_window: _Window, now: float, day: str
    ) -> None:
        if window.day != day:
            window.day = day
            window.day_count = 0
        if ip_window.day != day:
            ip_window.day = day
            ip_window.day_count = 0
        if now - window.minute_start >= 60:
            window.minute_start = now
            window.minute_count = 0
