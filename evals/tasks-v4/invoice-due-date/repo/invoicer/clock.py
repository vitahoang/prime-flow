"""The current time.

Everything that needs "now" goes through `now()` so the CLI can be pinned to a
fixed moment with INVOICER_NOW (an ISO-8601 timestamp, e.g.
2026-10-11T09:00:00Z). That is how the tests and the month-end dry runs work.
"""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config


def parse_instant(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    A timestamp without an offset is taken to be UTC.
    """
    raw = raw.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    value = datetime.fromisoformat(raw)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def now() -> datetime:
    """The current instant as an aware UTC datetime."""
    raw = os.environ.get(config.NOW_ENV)
    if raw:
        return parse_instant(raw)
    return datetime.now(timezone.utc)


def local_today(tz_name: str, at: datetime | None = None):
    """Today's date in the given IANA time zone."""
    instant = at if at is not None else now()
    return instant.astimezone(ZoneInfo(tz_name)).date()
