"""In-process chat limits and the exact answer cache, no network."""


from datetime import UTC, datetime

from app.api.cache import AnswerCache, cache_key, normalize_question
from app.api.limits import ChatLimiter, _Window
from app.config import Settings
from app.pipeline.generate import AskResult
from app.schemas import Chunk, ChunkMetadata


def _limiter(**overrides) -> ChatLimiter:
    return ChatLimiter(Settings(**overrides))


def test_minute_burst_is_limited():
    limiter = _limiter(chat_per_minute=2)
    assert limiter.admit("s", "ip").allowed
    assert limiter.admit("s", "ip").allowed
    decision = limiter.admit("s", "ip")
    assert decision.status == "rate_limited"
    assert decision.reason == "minute"
    assert 1 <= (decision.retry_after or 0) <= 60


def test_daily_cap_is_enforced():
    limiter = _limiter(chat_per_minute=100, chat_per_day=2)
    assert limiter.admit("s", "ip").allowed
    assert limiter.admit("s", "ip").allowed
    assert limiter.admit("s", "ip").reason == "day"


def test_per_ip_cap_catches_cookie_rotation():
    limiter = _limiter(chat_per_minute=100, chat_per_day=100, chat_ip_per_day=2)
    assert limiter.admit("s1", "ip").allowed
    assert limiter.admit("s2", "ip").allowed
    assert limiter.admit("s3", "ip").reason == "ip_day"


def test_concurrency_slot_is_released():
    limiter = _limiter(chat_concurrent=1)
    first = limiter.admit("s", "ip")
    assert first.allowed
    assert limiter.admit("s", "ip").reason == "concurrent"
    limiter.release(first.token)
    assert limiter.admit("s", "ip").allowed


def test_budget_degrades_instead_of_refusing(caplog):
    caplog.set_level("WARNING")
    limiter = _limiter(chat_daily_token_budget=10)
    assert limiter.admit("s", "ip").allowed
    limiter.record(8, 8)
    assert limiter.admit("s", "ip").status == "degraded"
    assert "chat budget at" in caplog.text


def test_cost_uses_the_configured_prices():
    limiter = _limiter(chat_input_price_per_mtok=1.0, chat_output_price_per_mtok=2.0)
    assert limiter.cost(1_000_000, 0) == 1.0
    assert limiter.cost(0, 1_000_000) == 2.0


def _result(answer: str = "Rowan [b1-c01-0000].") -> AskResult:
    chunk = Chunk(
        id="b1-c01-0000",
        text="Rowan trims the wick.",
        metadata=ChunkMetadata(
            book_num=1, chapter_num=1, book_name="Book 1", chapter_name="Chapter 1"
        ),
        score=1.0,
    )
    return AskResult(answer=answer, citations=["b1-c01-0000"], chunks=[chunk])


def test_question_normalisation_and_key_identity():
    assert normalize_question("  Who   trims the wick?! ") == "who trims the wick"
    assert cache_key("Who trims the wick?", "idx", "m") == cache_key(
        "who trims the wick", "idx", "m"
    )
    assert cache_key("q", "idx-a", "m") != cache_key("q", "idx-b", "m")
    assert cache_key("q", "idx", "m1") != cache_key("q", "idx", "m2")


def test_cache_hit_and_miss():
    cache = AnswerCache(max_entries=2, ttl_s=60)
    key = cache_key("q", "idx", "m")
    assert cache.get(key) is None
    cache.put(key, _result())
    assert cache.get(key) is not None


def test_cache_expires_and_evicts():
    now = [0.0]
    cache = AnswerCache(max_entries=1, ttl_s=10, clock=lambda: now[0])
    cache.put("a", _result())
    now[0] = 11.0
    assert cache.get("a") is None
    cache.put("b", _result())
    cache.put("c", _result())
    assert len(cache) == 1


def test_per_ip_minute_cap_catches_session_rotation():
    limiter = _limiter(chat_per_minute=1)
    assert limiter.admit("s1", "ip").allowed
    assert limiter.admit("s2", "ip").reason == "ip_minute"


def test_windows_roll_over():
    now = [0.0]
    day = [datetime(2026, 1, 1, tzinfo=UTC)]
    limiter = ChatLimiter(
        Settings(chat_per_minute=1, chat_concurrent=10),
        clock=lambda: now[0],
        now_utc=lambda: day[0],
    )
    assert limiter.admit("s", "ip").allowed
    assert limiter.admit("s", "ip").reason == "minute"
    now[0] = 61.0
    assert limiter.admit("s", "ip").allowed
    now[0] = 130.0
    day[0] = datetime(2026, 1, 2, tzinfo=UTC)
    limiter.record(10, 10)
    assert limiter.admit("s", "ip").allowed


def test_release_is_idempotent():
    limiter = _limiter(chat_concurrent=1)
    first = limiter.admit("s", "ip")
    second = limiter.admit("s", "ip")
    limiter.release(first.token)
    limiter.release(first.token)
    assert second.status == "rate_limited"
    assert limiter.admit("s", "ip").allowed


def test_client_ip_trusts_headers_only_from_a_trusted_peer():
    from starlette.requests import Request

    from app.main import _client_ip

    loopback = [__import__("ipaddress").ip_network("127.0.0.1/32")]
    scope = {
        "type": "http",
        "client": ("127.0.0.1", 1234),
        "headers": [(b"x-real-ip", b"203.0.113.9")],
    }
    assert _client_ip(Request(scope), loopback) == "203.0.113.9"

    direct = {
        "type": "http",
        "client": ("198.51.100.4", 1234),
        "headers": [(b"x-real-ip", b"203.0.113.9")],
    }
    assert _client_ip(Request(direct), loopback) == "198.51.100.4"


def test_rejected_session_does_not_grow_state():
    limiter = _limiter(chat_per_minute=1)
    assert limiter.admit("s1", "ip").allowed
    assert limiter.admit("s2", "ip").reason == "ip_minute"
    assert len(limiter._windows) == 1
    assert len(limiter._ip_windows) == 1


def test_capacity_refuses_without_evicting_live_windows():
    limiter = _limiter(chat_concurrent=100)
    day = limiter._today()
    limiter._windows = {
        f"s{i}": _Window(minute_start=0.0, minute_count=1, day=day, day_count=1)
        for i in range(20_000)
    }
    decision = limiter.admit("new-session", "new-ip")
    assert decision.reason == "capacity"
    assert len(limiter._windows) == 20_000


def test_default_proxies_trust_the_bridge_not_every_private_address():
    from ipaddress import ip_network

    from starlette.requests import Request

    from app.main import _client_ip

    default = Settings.model_fields["trusted_proxies"].default
    trusted = [ip_network(item) for item in default.split(",")]
    bridge = Request(
        {
            "type": "http",
            "client": ("172.17.0.1", 1),
            "headers": [(b"x-real-ip", b"203.0.113.9")],
        }
    )
    assert _client_ip(bridge, trusted) == "203.0.113.9"
    co_tenant = Request(
        {
            "type": "http",
            "client": ("172.17.0.2", 1),
            "headers": [(b"x-real-ip", b"203.0.113.9")],
        }
    )
    assert _client_ip(co_tenant, trusted) == "172.17.0.2"
    other = Request(
        {
            "type": "http",
            "client": ("172.20.0.5", 1),
            "headers": [(b"x-real-ip", b"203.0.113.9")],
        }
    )
    assert _client_ip(other, trusted) == "172.20.0.5"


def test_x_real_ip_wins_over_a_client_supplied_cf_header():
    from ipaddress import ip_network

    from starlette.requests import Request

    from app.main import _client_ip

    trusted = [ip_network("172.17.0.0/16")]
    request = Request(
        {
            "type": "http",
            "client": ("172.17.0.1", 1),
            "headers": [
                (b"cf-connecting-ip", b"1.2.3.4"),
                (b"x-real-ip", b"198.51.100.7"),
            ],
        }
    )
    assert _client_ip(request, trusted) == "198.51.100.7"


def test_prune_drops_current_day_empty_windows():
    limiter = _limiter()
    day = limiter._today()
    limiter._windows = {
        "empty": _Window(minute_start=0.0, minute_count=0, day=day, day_count=0),
        "live": _Window(minute_start=0.0, minute_count=1, day=day, day_count=1),
    }
    limiter._admits = 255
    limiter._maybe_prune(day)
    assert "empty" not in limiter._windows
    assert "live" in limiter._windows


def test_ip_capacity_refuses_without_evicting():
    limiter = _limiter(chat_concurrent=100)
    day = limiter._today()
    limiter._ip_windows = {
        f"ip{i}": _Window(minute_start=0.0, minute_count=1, day=day, day_count=1)
        for i in range(20_000)
    }
    decision = limiter.admit("new-session", "new-ip")
    assert decision.reason == "capacity"
    assert len(limiter._ip_windows) == 20_000


def test_cf_header_alone_is_ignored_even_from_the_proxy():
    from ipaddress import ip_network

    from starlette.requests import Request

    from app.main import _client_ip

    trusted = [ip_network("172.17.0.1/32")]
    request = Request(
        {
            "type": "http",
            "client": ("172.17.0.1", 1),
            "headers": [(b"cf-connecting-ip", b"1.2.3.4")],
        }
    )
    assert _client_ip(request, trusted) == "172.17.0.1"
