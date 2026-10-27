"""Recurring events: a Rule and the occurrences it generates."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .timeutil import require_aware

FREQUENCIES = ("daily", "weekly", "monthly")


@dataclass(frozen=True)
class Rule:
    freq: str
    start: datetime
    weekdays: frozenset = None

    def __post_init__(self):
        if self.freq not in FREQUENCIES:
            raise ValueError(f"freq must be one of {FREQUENCIES}, got {self.freq!r}")
        require_aware(self.start, "rule start")
        if self.weekdays is not None:
            object.__setattr__(self, "weekdays", frozenset(self.weekdays))


def _series_utc(rule):
    # Do the arithmetic in UTC so offsets never get mixed up.
    base = rule.start.astimezone(timezone.utc)
    if rule.freq == "daily":
        k = 0
        while True:
            yield base + timedelta(days=k)
            k += 1
    elif rule.freq == "weekly":
        wanted = rule.weekdays or {base.weekday()}
        k = 0
        while True:
            occ = base + timedelta(days=k)
            if occ.weekday() in wanted:
                yield occ
            k += 1
    else:
        k = 0
        while True:
            month = base.month - 1 + k
            try:
                yield base.replace(year=base.year + month // 12, month=month % 12 + 1)
            except ValueError:
                pass  # this month has no such day
            k += 1


def next_occurrences(rule, after, n):
    """The next ``n`` occurrences from ``after`` onwards."""
    require_aware(after, "after")
    after_utc = after.astimezone(timezone.utc)
    found = []
    if n <= 0:
        return found
    for occ in _series_utc(rule):
        if occ >= after_utc:
            found.append(occ.astimezone(rule.start.tzinfo))
            if len(found) == n:
                break
    return found
