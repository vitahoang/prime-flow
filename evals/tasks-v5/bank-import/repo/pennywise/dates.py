"""Date helpers.

Internally every date is a ``datetime.date`` and the database stores ISO
strings (YYYY-MM-DD). Bank exports use their own formats; see bank_profiles.
"""

import calendar
from datetime import date, datetime, timedelta

from .errors import InvalidInput

# Every bank we use exports day-first dates (DD/MM/YYYY), so that's the
# fallback whenever a format isn't given.
DEFAULT_FORMAT = "%d/%m/%Y"


def parse_date(text, fmt=None):
    """Parse a date in `fmt` (strptime syntax), or DEFAULT_FORMAT."""
    s = (text or "").strip()
    if not s:
        raise InvalidInput("empty date")
    try:
        return datetime.strptime(s, fmt or DEFAULT_FORMAT).date()
    except ValueError:
        raise InvalidInput(f"not a date in {fmt or DEFAULT_FORMAT}: {text!r}") from None


def parse_iso(text):
    try:
        return date.fromisoformat(text.strip())
    except (AttributeError, ValueError):
        raise InvalidInput(f"not a YYYY-MM-DD date: {text!r}") from None


def parse_month(text):
    """'2025-03' -> (2025, 3)."""
    try:
        year, month = text.strip().split("-")
        year, month = int(year), int(month)
    except (AttributeError, ValueError):
        raise InvalidInput(f"not a YYYY-MM month: {text!r}") from None
    if not 1 <= month <= 12:
        raise InvalidInput(f"not a YYYY-MM month: {text!r}")
    return year, month


def month_bounds(year, month):
    """First and last day of a month, inclusive."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def month_key(d):
    return f"{d.year:04d}-{d.month:02d}"


def iter_months(start, end):
    """Yield (year, month) from start's month to end's month inclusive."""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def days_between(a, b):
    return (b - a).days


def add_days(d, n):
    return d + timedelta(days=n)
