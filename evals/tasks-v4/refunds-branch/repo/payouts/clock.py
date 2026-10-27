"""Time helpers. Everything is stored as UTC ISO-8601 strings."""

from __future__ import annotations

from datetime import datetime, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def date_part(text: str) -> str:
    """'2026-10-19T08:30:00+00:00' -> '2026-10-19'."""
    return parse_iso(text).date().isoformat()
