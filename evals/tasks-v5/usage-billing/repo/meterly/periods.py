"""Billing periods.

A period is a pair of dates [start, end): end is exclusive, so September 2026
is (date(2026, 9, 1), date(2026, 10, 1)).
"""

import calendar
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator, Tuple
from zoneinfo import ZoneInfo


def month_period(year: int, month: int) -> Tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def previous_month(today: date) -> Tuple[date, date]:
    first = today.replace(day=1)
    last_month_end = first - timedelta(days=1)
    return month_period(last_month_end.year, last_month_end.month)


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def days(start: date, end: date) -> Iterator[date]:
    d = start
    while d < end:
        yield d
        d += timedelta(days=1)


def local_midnight(d: date, tz: str) -> datetime:
    """Midnight at the start of local day ``d`` in ``tz``, as a UTC datetime."""
    return datetime.combine(d, time(0), tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def period_bounds_utc(start: date, end: date, tz: str) -> Tuple[datetime, datetime]:
    """The UTC instants where a local [start, end) period begins and ends."""
    return local_midnight(start, tz), local_midnight(end, tz)


def local_date(dt: datetime, tz: str) -> date:
    return dt.astimezone(ZoneInfo(tz)).date()


def label(start: date, end: date) -> str:
    if start.day == 1 and end == month_period(start.year, start.month)[1]:
        return start.strftime("%B %Y")
    return f"{start.isoformat()} to {(end - timedelta(days=1)).isoformat()}"
