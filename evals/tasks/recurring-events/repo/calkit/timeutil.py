"""Small helpers for timezone-aware date arithmetic."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from . import settings


def zone(name):
    """Return the ZoneInfo for an IANA name such as ``"Europe/Paris"``."""
    return ZoneInfo(name)


def require_aware(dt, what="datetime"):
    """Raise ValueError unless ``dt`` is timezone-aware; return it otherwise."""
    if not isinstance(dt, datetime):
        raise TypeError(f"{what} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware")
    return dt


def zone_name(dt):
    """The IANA name of ``dt``'s zone, falling back to its abbreviation."""
    return getattr(dt.tzinfo, "key", None) or dt.tzname()


def local_date(dt, tz):
    """The calendar date of the instant ``dt`` as seen in ``tz``."""
    return dt.astimezone(tz).date()


def start_of_day(day, tz):
    """Midnight at the start of ``day`` in ``tz``."""
    return datetime.combine(day, time(0), tzinfo=tz)


def end_of_day(day, tz):
    """Midnight at the start of the day after ``day`` in ``tz`` (exclusive)."""
    return start_of_day(day + timedelta(days=1), tz)


def start_of_week(day, week_start=None):
    """The first date of the week containing ``day``.

    ``week_start`` defaults to ``settings.WEEK_START``.
    """
    first = settings.WEEK_START if week_start is None else week_start
    return day - timedelta(days=(day.weekday() - first) % 7)


def iter_days(first, last):
    """Yield every date from ``first`` to ``last`` inclusive."""
    day = first
    while day <= last:
        yield day
        day += timedelta(days=1)


def as_date(value):
    """Accept a date or an ISO string ``YYYY-MM-DD`` and return a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
