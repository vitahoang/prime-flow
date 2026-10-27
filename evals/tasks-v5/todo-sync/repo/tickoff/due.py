"""Turning what people type ("tomorrow", "fri", "+3", "11/03") into ISO dates."""

from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


class DueParseError(ValueError):
    pass


def parse_due(text: str, today: date) -> str | None:
    """Parse a due date relative to `today`. Returns an ISO date or None for
    'none' / 'never' / ''."""
    raw = (text or "").strip().lower()
    if raw in ("", "none", "never", "-"):
        return None
    if raw in ("today", "tod"):
        return today.isoformat()
    if raw in ("tomorrow", "tmr", "tom"):
        return (today + timedelta(days=1)).isoformat()
    if raw in ("next week", "nw"):
        return (today + timedelta(days=7 - today.weekday())).isoformat()
    m = re.fullmatch(r"\+(\d{1,3})([dw]?)", raw)
    if m:
        n = int(m.group(1)) * (7 if m.group(2) == "w" else 1)
        return (today + timedelta(days=n)).isoformat()
    for i, name in enumerate(WEEKDAYS):
        if raw == name or (len(raw) >= 3 and _full_day(i).startswith(raw)):
            ahead = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=ahead)).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return _checked(int(m.group(1)), int(m.group(2)), int(m.group(3)), text)
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", raw)
    if m:
        # month/day, the US way, because that is how the old app did it
        return _next_occurrence(today, int(m.group(1)), int(m.group(2)), text)
    m = re.fullmatch(r"(\d{1,2})\s*([a-z]{3})[a-z]*", raw) or re.fullmatch(r"([a-z]{3})[a-z]*\s*(\d{1,2})", raw)
    if m:
        a, b = m.groups()
        day_s, mon_s = (a, b) if a.isdigit() else (b, a)
        if mon_s in MONTHS:
            return _next_occurrence(today, MONTHS.index(mon_s) + 1, int(day_s), text)
    raise DueParseError(f"can't read due date {text!r}")


def _full_day(i: int) -> str:
    return ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][i]


def _checked(y: int, m: int, d: int, text: str) -> str:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        raise DueParseError(f"no such date: {text!r}") from None


def _next_occurrence(today: date, month: int, day: int, text: str) -> str:
    """This year's date, or next year's if it has already passed."""
    iso = _checked(today.year, month, day, text)
    if iso < today.isoformat():
        iso = _checked(today.year + 1, month, day, text)
    return iso


def describe(due: str | None, today: date) -> str:
    """Short human form for listings: 'today', 'tomorrow', 'in 3d', '2d late'."""
    if not due:
        return ""
    delta = (date.fromisoformat(due) - today).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta == -1:
        return "yesterday"
    if delta < 0:
        return f"{-delta}d late"
    if delta < 7:
        return WEEKDAYS[date.fromisoformat(due).weekday()]
    return due
