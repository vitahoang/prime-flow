"""Recurring events: a Rule and the occurrences it generates.

Occurrences keep the wall-clock time of ``rule.start`` in its own timezone, so
a 07:00 class stays at 07:00 local across daylight-saving changes. Monthly
rules on a day a month lacks (e.g. the 31st) fall on that month's last day.
"""

import calendar as _stdcal
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .timeutil import require_aware

FREQUENCIES = ("daily", "weekly", "monthly")


@dataclass(frozen=True)
class Rule:
    freq: str
    start: datetime
    weekdays: frozenset = None
    exceptions: frozenset = frozenset()  # local dates whose occurrence is cancelled
    until: date = None                   # last local date of the series, inclusive
    count: int = None                    # total occurrences in the series

    def __post_init__(self):
        if self.freq not in FREQUENCIES:
            raise ValueError(f"freq must be one of {FREQUENCIES}, got {self.freq!r}")
        require_aware(self.start, "rule start")
        if self.weekdays is not None:
            days = frozenset(self.weekdays)
            if not days or not days <= set(range(7)):
                raise ValueError("weekdays must be a non-empty set of ints 0..6")
            object.__setattr__(self, "weekdays", days)
        object.__setattr__(self, "exceptions", frozenset(self.exceptions or ()))
        if self.count is not None and self.count < 0:
            raise ValueError("count must not be negative")


def _local_dates(rule):
    first = rule.start.date()
    if rule.freq == "daily":
        day = first
        while True:
            yield day
            day += timedelta(days=1)
    elif rule.freq == "weekly":
        wanted = rule.weekdays or {first.weekday()}
        day = first
        while True:
            if day.weekday() in wanted:
                yield day
            day += timedelta(days=1)
    else:
        year, month = first.year, first.month
        while True:
            last = _stdcal.monthrange(year, month)[1]
            yield date(year, month, min(first.day, last))
            month += 1
            if month == 13:
                year, month = year + 1, 1


def _series(rule):
    """Every occurrence of the rule in order, cancelled ones included."""
    tz, wall = rule.start.tzinfo, rule.start.timetz().replace(tzinfo=None)
    for index, day in enumerate(_local_dates(rule)):
        if rule.until is not None and day > rule.until:
            return
        if rule.count is not None and index >= rule.count:
            return
        yield datetime.combine(day, wall, tzinfo=tz)


def next_occurrences(rule, after, n):
    """The next ``n`` occurrences strictly after ``after`` (fewer if the series ends)."""
    require_aware(after, "after")
    found = []
    if n <= 0:
        return found
    for occ in _series(rule):
        if occ.date() in rule.exceptions or occ <= after:
            continue
        found.append(occ)
        if len(found) == n:
            break
    return found
