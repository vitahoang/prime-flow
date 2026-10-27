"""Clocks. Everything in alertd asks a clock for the time so tests can control it.

A clock has one method, ``now()``, returning a timezone-aware datetime in UTC.
"""

from datetime import datetime, timedelta, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """A clock that only moves when told to."""

    def __init__(self, start: datetime | None = None):
        if start is None:
            start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        if start.tzinfo is None:
            raise ValueError("FakeClock needs a timezone-aware start time")
        self._now = start.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float = 0, minutes: float = 0, hours: float = 0) -> datetime:
        self._now += timedelta(seconds=seconds, minutes=minutes, hours=hours)
        return self._now

    def set(self, when: datetime) -> None:
        if when.tzinfo is None:
            raise ValueError("FakeClock.set needs a timezone-aware time")
        self._now = when.astimezone(timezone.utc)
