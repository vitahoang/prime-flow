"""Selecting entries."""

from datetime import date, datetime, time, timezone
from typing import Iterable, List, Optional

from ledger.models import Entry


def parse_date(value: str) -> datetime:
    """Parse a ``YYYY-MM-DD`` command-line date as midnight UTC."""
    d = date.fromisoformat(value)
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def in_range(
    entries: Iterable[Entry],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Entry]:
    """Entries with ``start <= when < end``. Either bound may be omitted."""
    result = []
    for entry in entries:
        when = entry.when
        if start is not None and when < start:
            continue
        if end is not None and when >= end:
            continue
        result.append(entry)
    return result


def active(entries: Iterable[Entry]) -> List[Entry]:
    return [e for e in entries if not e.archived]


def by_category(entries: Iterable[Entry], category: str) -> List[Entry]:
    return [e for e in entries if e.category == category]


def total_cents(entries: Iterable[Entry]) -> int:
    return sum(e.amount_cents for e in entries)
