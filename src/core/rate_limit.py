import time
from collections import deque

from fastapi import Request, Response

from src.core.exceptions import RateLimitExceededError


class RateLimiter:
    def __init__(self, calls: int, period: int = 60) -> None:
        self.calls = calls
        self.period = period
        self._store: dict[str, deque[float]] = {}

    async def __call__(self, request: Request, response: Response) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._store.setdefault(key, deque())

        while window and window[0] < now - self.period:
            window.popleft()

        remaining = self.calls - len(window)
        reset_ts = int(time.time()) + self.period
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining - 1))
        response.headers["X-RateLimit-Reset"] = str(reset_ts)

        if len(window) >= self.calls:
            retry = int(self.period - (now - window[0])) + 1
            raise RateLimitExceededError(retry_after=retry)

        window.append(now)
