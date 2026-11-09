"""In-process chat limits, usage accounting and the daily spend guard.

One API process on one host, so memory is enough; a restart resets the windows.
Chat only: exam routes will use their own dependency, so degrading chat never
takes them down.

Sessions are server-issued and signed in the API layer; this module only keys on
the value it is given. Releases use a per-admission token, so a double release
cannot free another request's slot.
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.config import Settings

logger = logging.getLogger(__name__)

DecisionStatus = Literal["ok", "rate_limited", "degraded"]


@dataclass(frozen=True)
class Decision:
    """Admission outcome for one chat request."""

    status: DecisionStatus
    reason: str | None = None
    retry_after: int | None = None
    token: str | None = None

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
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._clock = clock
        self._now_utc = now_utc or (lambda: datetime.now(UTC))
        self._windows: dict[str, _Window] = {}
        self._ip_windows: dict[str, _Window] = {}
        self._active: dict[str, set[str]] = {}
        self._active_ip: dict[str, set[str]] = {}
        self._leases: dict[str, tuple[str, str]] = {}
        self._admits = 0
        self._tokens_day = ""
        self._tokens = 0
        self._alerts: set[int] = set()

    def admit(self, session: str, ip: str, *, cache_hit: bool = False) -> Decision:
        """Check the limits and, when allowed, count the request."""
        now = self._clock()
        day = self._today()
        self._roll_day(day)
        self._maybe_prune(day)
        window = self._windows.get(session)
        ip_window = self._ip_windows.get(ip)
        if window is not None:
            self._roll(window, now, day)
        if ip_window is not None:
            self._roll(ip_window, now, day)

        session_minute = window.minute_count if window else 0
        ip_minute = ip_window.minute_count if ip_window else 0
        session_day = window.day_count if window else 0
        ip_day = ip_window.day_count if ip_window else 0
        session_retry = max(
            1, math.ceil(60 - (now - (window.minute_start if window else now)))
        )
        ip_retry = max(
            1, math.ceil(60 - (now - (ip_window.minute_start if ip_window else now)))
        )
        if session_minute >= self._settings.chat_per_minute:
            return Decision("rate_limited", "minute", session_retry)
        if ip_minute >= self._settings.chat_per_minute:
            return Decision("rate_limited", "ip_minute", ip_retry)
        if session_day >= self._settings.chat_per_day:
            return Decision("rate_limited", "day", self._to_midnight())
        if ip_day >= self._settings.chat_ip_per_day:
            return Decision("rate_limited", "ip_day", self._to_midnight())
        if len(self._active.get(session, ())) >= self._settings.chat_concurrent:
            return Decision("rate_limited", "concurrent", 1)
        if len(self._active_ip.get(ip, ())) >= self._settings.chat_concurrent:
            return Decision("rate_limited", "ip_concurrent", 1)
        if not cache_hit and self._tokens >= self._settings.chat_daily_token_budget:
            return Decision("degraded", "budget", self._to_midnight())

        # Only create state for an admitted request; a rejection must not grow
        # the maps, or cheap rejected identities could exhaust capacity.
        if len(self._windows) >= 20_000 and window is None:
            return Decision("rate_limited", "capacity", self._to_midnight())
        if len(self._ip_windows) >= 20_000 and ip_window is None:
            return Decision("rate_limited", "capacity", self._to_midnight())
        if window is None:
            window = self._windows[session] = _Window(minute_start=now, day=day)
        if ip_window is None:
            ip_window = self._ip_windows[ip] = _Window(minute_start=now, day=day)

        token = uuid.uuid4().hex
        window.minute_count += 1
        window.day_count += 1
        ip_window.minute_count += 1
        ip_window.day_count += 1
        self._active.setdefault(session, set()).add(token)
        self._active_ip.setdefault(ip, set()).add(token)
        self._leases[token] = (session, ip)
        return Decision("ok", token=token)

    def release(self, token: str | None) -> None:
        """Release one admission. Safe to call twice."""
        if token is None:
            return
        lease = self._leases.pop(token, None)
        if lease is None:
            return
        session, ip = lease
        self._active.get(session, set()).discard(token)
        if not self._active.get(session):
            self._active.pop(session, None)
        self._active_ip.get(ip, set()).discard(token)
        if not self._active_ip.get(ip):
            self._active_ip.pop(ip, None)

    def cost(self, input_tokens: int, output_tokens: int, *, small: bool = False) -> float:
        prices = self._settings
        input_price = (
            prices.chat_small_input_price_per_mtok
            if small
            else prices.chat_input_price_per_mtok
        )
        output_price = (
            prices.chat_small_output_price_per_mtok
            if small
            else prices.chat_output_price_per_mtok
        )
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

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
        self._roll_day(self._today())
        return self._tokens

    def _today(self) -> str:
        return self._now_utc().strftime("%Y-%m-%d")

    def _to_midnight(self) -> int:
        now = self._now_utc()
        seconds = 24 * 3600 - (now.hour * 3600 + now.minute * 60 + now.second)
        return max(60, seconds)

    def _roll_day(self, day: str) -> None:
        if self._tokens_day == day:
            return
        self._tokens_day = day
        self._tokens = 0
        self._alerts.clear()

    def _roll(self, window: _Window, now: float, day: str) -> None:
        if window.day != day:
            window.day = day
            window.day_count = 0
        if now - window.minute_start >= 60:
            window.minute_start = now
            window.minute_count = 0

    def _maybe_prune(self, day: str) -> None:
        """Drop yesterday's windows and empty sessions so headers cannot grow state."""
        self._admits += 1
        if self._admits % 256:
            return
        self._windows = {
            key: window for key, window in self._windows.items() if window.day == day
        }
        self._ip_windows = {
            key: window for key, window in self._ip_windows.items() if window.day == day
        }
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if window.day == day and (window.minute_count or window.day_count)
        }
        self._ip_windows = {
            key: window
            for key, window in self._ip_windows.items()
            if window.day == day and (window.minute_count or window.day_count)
        }


class ExamAttemptLimiter:
    """Per-session daily attempt cap; signed-in identities get the larger limit."""

    def __init__(
        self,
        settings: Settings,
        *,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._now_utc = now_utc or (lambda: datetime.now(UTC))
        self._counts: dict[str, tuple[str, int]] = {}

    def admit(self, identity: str, *, signed_in: bool = False) -> Decision:
        """Count one attempt or return the daily limit decision."""
        day = self._now_utc().strftime("%Y-%m-%d")
        limit = (
            self._settings.exam_attempts_per_day_signed_in
            if signed_in
            else self._settings.exam_attempts_per_day_anonymous
        )
        current_day, count = self._counts.get(identity, (day, 0))
        if current_day != day:
            current_day = day
            count = 0
        if count >= limit:
            return Decision("rate_limited", "exam_day", self._to_midnight())
        self._counts[identity] = (current_day, count + 1)
        return Decision("ok")

    def _to_midnight(self) -> int:
        now = self._now_utc()
        seconds = 24 * 3600 - (now.hour * 3600 + now.minute * 60 + now.second)
        return max(60, seconds)
