import time
from collections import deque

import pytest

from src.core.exceptions import RateLimitExceededError
from src.core.rate_limit import RateLimiter


class _FakeClient:
    host = "127.0.0.1"


class _FakeRequest:
    client = _FakeClient()


class _FakeResponse:
    headers: dict[str, str] = {}

    def __init__(self) -> None:
        self.headers = {}


@pytest.mark.asyncio
async def test_allows_under_limit() -> None:
    limiter = RateLimiter(calls=3)
    for _ in range(3):
        await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_blocks_over_limit() -> None:
    limiter = RateLimiter(calls=3)
    for _ in range(3):
        await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]
    with pytest.raises(RateLimitExceededError):
        await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rate_limit_headers() -> None:
    limiter = RateLimiter(calls=5)
    response = _FakeResponse()
    await limiter(_FakeRequest(), response)  # type: ignore[arg-type]
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert response.headers["X-RateLimit-Limit"] == "5"


@pytest.mark.asyncio
async def test_retry_after_in_exception() -> None:
    limiter = RateLimiter(calls=1)
    await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]
    assert exc_info.value.retry_after > 0


@pytest.mark.asyncio
async def test_window_resets() -> None:
    limiter = RateLimiter(calls=2, period=1)
    for _ in range(2):
        await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]
    # simulate time passing beyond the window
    key = "127.0.0.1"
    limiter._store[key] = deque([time.monotonic() - 2])  # expired entry
    # should allow again
    await limiter(_FakeRequest(), _FakeResponse())  # type: ignore[arg-type]
