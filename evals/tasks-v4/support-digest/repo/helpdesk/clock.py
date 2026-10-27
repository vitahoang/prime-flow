"""Clocks.

Everything that needs the current time takes a clock instead of calling
``datetime.now()`` directly, so tests can control time. Every clock returns a
timezone-aware datetime in UTC.
"""

from datetime import datetime, timedelta, timezone


class Clock:
    def now(self) -> datetime:
        raise NotImplementedError


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock(Clock):
    """A clock that only moves when told to."""

    def __init__(self, start: datetime):
        if start.tzinfo is None:
            raise ValueError("FakeClock needs an aware datetime")
        self._now = start.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def set(self, when: datetime) -> None:
        if when.tzinfo is None:
            raise ValueError("FakeClock needs an aware datetime")
        self._now = when.astimezone(timezone.utc)

    def advance(self, **kwargs) -> datetime:
        """Move forward, e.g. ``advance(minutes=15)``. Returns the new time."""
        delta = timedelta(**kwargs)
        if delta < timedelta(0):
            raise ValueError("time only moves forward")
        self._now += delta
        return self._now
