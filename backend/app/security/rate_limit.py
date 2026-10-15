"""In-memory sliding-window rate limiter (per IP + route scope)."""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, limit: int, window_s: int = 60) -> tuple[bool, int]:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - window_s:
                q.popleft()
            if len(q) >= limit:
                retry_after = int(q[0] + window_s - now) + 1
                return False, max(retry_after, 1)
            q.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()
