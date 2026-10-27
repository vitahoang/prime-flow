"""Calendar helpers for invoices: terms, due dates, lateness.

Everything that needs "when is this invoice due?" should go through
local_due_date() so the CLI, reminders and late fees always agree.
"""

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_TERMS_RE = re.compile(r"^\s*(?:net)?[\s\-]*(\d{1,3})\s*(?:days?)?\s*$", re.I)


def parse_terms(raw) -> int:
    """'Net 30', 'net-15', '30', 30 -> number of days."""
    if isinstance(raw, int):
        return raw
    if raw is None or str(raw).strip() == "":
        raise ValueError("missing payment terms")
    text = str(raw)
    if text.strip().lower() in ("due on receipt", "on receipt"):
        return 0
    m = _TERMS_RE.match(text)
    if not m:
        raise ValueError(f"unrecognised payment terms: {raw!r}")
    return int(m.group(1))


def format_terms(days: int) -> str:
    return "Due on receipt" if days == 0 else f"Net {days}"


def to_calendar_date(value) -> date:
    """The calendar date of an issue timestamp (or a plain date)."""
    # All timestamps are local: they're written on the studio laptop when the
    # invoice is raised, so the date part is already the right calendar day.
    if isinstance(value, datetime):
        return value.date()
    return value


def local_due_date(issued, terms_days: int, tz_name: str | None = None) -> date:
    """The day an invoice falls due, in the customer's own calendar.

    `issued` is the invoice's issue timestamp (or, for v0 records, its issue
    date). `tz_name` is the customer's IANA zone; it is accepted for callers
    that pass it but not needed, see to_calendar_date().
    """
    return to_calendar_date(issued) + timedelta(days=terms_days)


def end_of_local_day(day: date, tz_name: str) -> datetime:
    """The instant (UTC) at which `day` ends in the given zone."""
    tz = ZoneInfo(tz_name)
    midnight = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz)
    return midnight.astimezone(timezone.utc)


def days_late(due: date, today: date) -> int:
    return max(0, (today - due).days)


def days_until(due: date, today: date) -> int:
    return (due - today).days


def reminder_date(due: date, days_before: int) -> date:
    return due - timedelta(days=days_before)


def aging_bucket(days: int) -> str:
    """Statement aging column for a number of days past due."""
    if days <= 0:
        return "current"
    if days <= 30:
        return "1-30"
    if days <= 60:
        return "31-60"
    return "60+"


def add_business_days(start: date, n: int) -> date:
    """start + n working days (Mon-Fri). Was used for 'Net 10 business days'
    terms, which nobody has asked for since 2024."""
    day = start
    while n > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def month_bounds(year: int, month: int) -> tuple[date, date]:
    first = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    return first, nxt - timedelta(days=1)
