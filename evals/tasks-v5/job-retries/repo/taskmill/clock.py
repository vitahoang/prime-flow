"""Time, behind a seam.

Everything in taskmill that needs "now" asks a ``Clock``. Production code uses
``SystemClock``; tests use ``FakeClock`` and move time by hand, so nothing in
the test suite ever sleeps for real.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol

#: 2026-01-01T00:00:00Z. FakeClock starts here unless told otherwise.
EPOCH_2026 = 1_767_225_600.0


class Clock(Protocol):
    def now(self) -> float:
        """Current time as a UNIX timestamp in seconds."""

    def sleep(self, seconds: float) -> None:
        """Wait (or pretend to wait) for ``seconds``."""


class SystemClock:
    """The real wall clock."""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)

    def __repr__(self) -> str:
        return "SystemClock()"


class FakeClock:
    """A clock that only moves when you move it.

    ``sleep`` advances the clock instead of blocking, so a worker loop driven
    by a FakeClock runs as fast as the CPU allows.
    """

    def __init__(self, start: float = EPOCH_2026):
        self._now = float(start)
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("FakeClock cannot go backwards")
        self._now += seconds
        return self._now

    def set(self, when: float) -> None:
        if when < self._now:
            raise ValueError("FakeClock cannot go backwards")
        self._now = float(when)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if seconds > 0:
            self._now += seconds

    def __repr__(self) -> str:
        return f"FakeClock({format_ts(self._now)})"


def format_ts(ts: float | None) -> str:
    """Render a timestamp the way the CLI prints it (UTC, seconds)."""
    if ts is None:
        return "-"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(text: str) -> float:
    """Parse an ISO-8601 date or datetime. Naive values are taken as UTC."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()
