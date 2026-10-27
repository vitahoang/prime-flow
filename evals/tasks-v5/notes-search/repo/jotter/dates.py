"""Dates in front matter.

`created` and `updated` are ISO 8601 local times without a zone, e.g.
`2024-03-02T09:15:00`. Older notes (before 0.6) have a bare date,
`2024-03-02`, which reads as midnight.
"""

from datetime import date, datetime

FORMAT = "%Y-%m-%dT%H:%M:%S"


class BadDate(ValueError):
    pass


def parse(value):
    """Parse a front-matter date. Returns None for missing/empty values."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value).strip()
    try:
        if len(text) == 10:
            return datetime.strptime(text, "%Y-%m-%d")
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError as exc:
        raise BadDate(f"not a date: {value!r}") from exc


def format(dt):
    return dt.strftime(FORMAT)


def short(dt):
    """2024-03-02, for listings."""
    return dt.strftime("%Y-%m-%d") if dt else "-"


def humanize(dt, now):
    """'today', 'yesterday', '3 days ago', '5 weeks ago', '2 years ago'."""
    if dt is None:
        return "never"
    days = (now.date() - dt.date()).days
    if days < 0:
        return "in the future"
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"
