"""Queries over stored usage events."""

from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from .models import UsageEvent
from .store import Store


def events_for(store: Store, customer_id: str, start: datetime, end: datetime) -> List[UsageEvent]:
    """Events for a customer whose timestamp is in [start, end). Both ends are aware datetimes."""
    return sorted(
        (e for e in store.events if e.customer_id == customer_id and start <= e.timestamp < end),
        key=lambda e: e.timestamp,
    )


def count_calls(events: Iterable[UsageEvent]) -> int:
    """Number of API calls in ``events``."""
    return sum(1 for _ in events)


def by_metric(events: Iterable[UsageEvent]) -> Dict[str, List[UsageEvent]]:
    out = defaultdict(list)
    for e in events:
        out[e.metric].append(e)
    return dict(out)


def daily_counts(events: Iterable[UsageEvent], tz: str = "UTC") -> Dict[date, int]:
    """Calls per local day, for the usage chart."""
    zone = ZoneInfo(tz)
    counts = Counter()
    for e in events:
        counts[e.timestamp.astimezone(zone).date()] += 1
    return dict(sorted(counts.items()))


def last_seen(store: Store, customer_id: str) -> Optional[datetime]:
    stamps = [e.timestamp for e in store.events if e.customer_id == customer_id]
    return max(stamps) if stamps else None


def sources(events: Iterable[UsageEvent]) -> Dict[str, int]:
    """How many events came from each source (sdk, batch, import)."""
    return dict(Counter(e.source for e in events))


def busiest_hour(events: Iterable[UsageEvent], tz: str = "UTC") -> Optional[int]:
    zone = ZoneInfo(tz)
    hours = Counter(e.timestamp.astimezone(zone).hour for e in events)
    if not hours:
        return None
    return hours.most_common(1)[0][0]
