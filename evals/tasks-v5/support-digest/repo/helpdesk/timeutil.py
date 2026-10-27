"""Small date/time helpers shared across the package.

Storage is always aware UTC. Conversion to an agent's own timezone happens
only at the edges (emails, reports).
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError(f"naive datetime not allowed: {dt!r}")
    return dt.astimezone(UTC)


def parse_iso(text: str) -> datetime:
    """Parse an ISO-8601 timestamp written by ``format_iso``."""
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return ensure_aware(datetime.fromisoformat(text))


def format_iso(dt: datetime) -> str:
    return ensure_aware(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown timezone: {name!r}") from exc


def to_local(dt: datetime, tz_name: str) -> datetime:
    """Convert an aware datetime into the named IANA timezone."""
    return ensure_aware(dt).astimezone(zone(tz_name))


def local_date(dt: datetime, tz_name: str) -> date:
    return to_local(dt, tz_name).date()


def format_local(dt: datetime, tz_name: str) -> str:
    """Human-readable local time, e.g. ``Wed 14 Oct 10:30 (Europe/London)``."""
    local = to_local(dt, tz_name)
    return f"{local:%a %d %b %H:%M} ({tz_name})"


def hours_between(start: datetime, end: datetime) -> float:
    return (ensure_aware(end) - ensure_aware(start)) / timedelta(hours=1)


def start_of_utc_day(dt: datetime) -> datetime:
    dt = ensure_aware(dt)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def humanize_age(delta: timedelta) -> str:
    """``timedelta(hours=26)`` -> ``"1d 2h"``; under an hour -> ``"45m"``."""
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 60:
        return f"{max(total_minutes, 0)}m"
    days, rem = divmod(total_minutes, 24 * 60)
    hours = rem // 60
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    return f"{hours}h"
