"""In-process rate limiting in front of every Gemini call.

A public URL with no throttle is an open invitation to run up the API bill or
exhaust the free host's quota. This is a per-instance, per-session sliding
window — deliberately simple. Limitation (documented): it does not coordinate
across multiple server processes; the free-host single-instance topology this
project targets makes that acceptable, and the cost of a bypass is bounded by
the per-call token cap in config.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimitState:
    calls: deque[float] = field(default_factory=deque)


class RateLimiter:
    """Sliding-window rate limiter: at most ``max_calls`` per ``per_seconds``."""

    def __init__(self, max_calls: int = 5, per_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._lock = threading.Lock()
        self._sessions: dict[str, RateLimitState] = {}

    def _session(self, session_key: str) -> RateLimitState:
        """Get-or-create the session state. Caller MUST hold ``self._lock``
        (``check`` acquires it) — using a plain Lock here too would deadlock,
        which is exactly the bug the hanging tests exposed."""
        if session_key not in self._sessions:
            # bounded map: drop stale sessions when it grows past 1000
            if len(self._sessions) > 1000:
                cutoff = time.monotonic() - self.per_seconds
                self._sessions = {
                    k: v for k, v in self._sessions.items()
                    if v.calls and v.calls[-1] > cutoff
                }
            self._sessions[session_key] = RateLimitState()
        return self._sessions[session_key]

    def check(self, session_key: str = "default") -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``. Records the call if allowed."""
        now = time.monotonic()
        with self._lock:
            state = self._session(session_key)
            window_start = now - self.per_seconds
            while state.calls and state.calls[0] < window_start:
                state.calls.popleft()
            if len(state.calls) >= self.max_calls:
                retry_after = self.per_seconds - (now - state.calls[0])
                return False, max(retry_after, 0.0)
            state.calls.append(now)
            return True, 0.0


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limit exceeded; retry after {retry_after:.1f}s")
        self.retry_after = retry_after


def enforce(limiter: RateLimiter, session_key: str = "default") -> None:
    """Check and raise :class:`RateLimitExceeded` if the session is throttled."""
    allowed, retry_after = limiter.check(session_key)
    if not allowed:
        raise RateLimitExceeded(retry_after)
