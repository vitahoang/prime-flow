"""Clocks.

A replica keeps two kinds of time:

* a Lamport counter (LamportClock). It goes up by one on every local change,
  and each change-log entry carries the value it got;
* wall time, the device's own idea of "now" (SystemWall). Each change-log
  entry stores it as `wall`, and tasks keep created_at / updated_at.

Wall times are ISO 8601 UTC strings with second precision, so they sort as
strings.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WALL_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def format_wall(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(WALL_FORMAT)


def parse_wall(text: str) -> datetime:
    return datetime.strptime(text, WALL_FORMAT).replace(tzinfo=timezone.utc)


class LamportClock:
    """A Lamport counter."""

    def __init__(self, value: int = 0):
        self.value = int(value)

    def tick(self) -> int:
        """Advance for a local change and return the new value."""
        self.value += 1
        return self.value

    def observe(self, other: int) -> int:
        """Move past a counter seen on another device's change."""
        if other > self.value:
            self.value = int(other)
        return self.value

    def __repr__(self):
        return f"LamportClock({self.value})"


class SystemWall:
    """The device clock. `skew_seconds` is only for trying things out."""

    def __init__(self, skew_seconds: float = 0):
        self.skew = timedelta(seconds=skew_seconds)

    def now(self) -> str:
        return format_wall(datetime.now(timezone.utc) + self.skew)


class ManualWall:
    """A wall clock that only moves when told to. Used by tests and scripts."""

    def __init__(self, start: str = "2026-01-05T09:00:00Z"):
        self._moment = parse_wall(start)

    def now(self) -> str:
        return format_wall(self._moment)

    def advance(self, seconds: float = 60) -> str:
        self._moment += timedelta(seconds=seconds)
        return self.now()

    def set(self, text: str) -> None:
        self._moment = parse_wall(text)


def today(wall) -> str:
    """The date part of the wall clock's now()."""
    return wall.now()[:10]
