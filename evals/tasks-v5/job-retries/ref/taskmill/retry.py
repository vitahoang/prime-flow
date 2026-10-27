"""When to try a failed job again.

Exponential backoff: 30s after the first failure, doubling each time, never
more than an hour, plus up to 10% random jitter so workers that failed
together don't all come back in the same second. Five attempts in total
(counting the first run), then the job is dead. ``PermanentError`` is never
retried. ``RateLimited`` waits at least as long as the remote asked.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .errors import PermanentError, RateLimited


@dataclass
class RetryPolicy:
    max_attempts: int = 5
    base: float = 30.0
    cap: float = 3600.0
    jitter: float = 0.10
    rng: random.Random = field(default_factory=random.Random, repr=False)

    def backoff(self, attempt: int) -> float:
        """Delay after the ``attempt``-th failed attempt (1-based)."""
        delay = min(self.base * 2 ** (attempt - 1), self.cap)
        return delay + delay * self.rng.uniform(0, self.jitter)

    def next_delay(self, attempts: int, exc: BaseException) -> float | None:
        """Seconds until the next attempt, or None to give up."""
        if isinstance(exc, PermanentError):
            return None
        if attempts >= self.max_attempts:
            return None
        delay = self.backoff(attempts)
        if isinstance(exc, RateLimited):
            delay = max(delay, exc.retry_after)
        return delay
