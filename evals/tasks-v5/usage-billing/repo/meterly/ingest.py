"""Usage ingest: what the HTTP endpoint calls for each request from an SDK.

We store whatever arrives; ingest is append-only and never rewrites
events.jsonl.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config
from .models import UsageEvent
from .store import Store


class IngestError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _check(store: Store, customer_id: str, timestamp: datetime, now: datetime):
    if customer_id not in store.customers:
        raise IngestError(f"unknown customer {customer_id!r}")
    if timestamp.tzinfo is None:
        raise IngestError("timestamp must be timezone-aware")
    if timestamp - now > timedelta(seconds=config.MAX_CLOCK_SKEW_SECONDS):
        raise IngestError("timestamp is in the future")


def record_call(store: Store, customer_id: str, *, event_id: Optional[str] = None,
                timestamp: Optional[datetime] = None, now: Optional[datetime] = None,
                metric: str = config.DEFAULT_METRIC) -> UsageEvent:
    """Store a single API call."""
    now = now or _now()
    timestamp = timestamp or now
    _check(store, customer_id, timestamp, now)
    event = UsageEvent(
        event_id=event_id or f"evt_{uuid.uuid4().hex[:16]}",
        customer_id=customer_id,
        timestamp=timestamp.astimezone(timezone.utc),
        received_at=now,
        units=1,
        metric=metric,
        source="sdk",
    )
    store.append_event(event)
    return event


def record_batch(store: Store, customer_id: str, units: int, *, event_id: Optional[str] = None,
                 timestamp: Optional[datetime] = None, now: Optional[datetime] = None,
                 metric: str = config.DEFAULT_METRIC) -> UsageEvent:
    """Store a batch from the SDK's buffer.

    High-volume customers turn on buffering: the SDK counts calls locally and
    flushes one event every minute with ``units`` set to the number of calls.
    ``timestamp`` is the start of the buffered minute.
    """
    if units < 1:
        raise IngestError("a batch needs at least one unit")
    now = now or _now()
    timestamp = timestamp or now
    _check(store, customer_id, timestamp, now)
    event = UsageEvent(
        event_id=event_id or f"evt_{uuid.uuid4().hex[:16]}",
        customer_id=customer_id,
        timestamp=timestamp.astimezone(timezone.utc),
        received_at=now,
        units=units,
        metric=metric,
        source="batch",
    )
    store.append_event(event)
    return event


def handle_request(store: Store, customer_id: str, payload: dict, now: Optional[datetime] = None) -> UsageEvent:
    """Entry point for the HTTP handler. ``payload`` is the request JSON."""
    ts = payload.get("timestamp")
    timestamp = None
    if ts:
        from .models import parse_ts
        timestamp = parse_ts(ts)
    units = int(payload.get("units", 1))
    kwargs = dict(event_id=payload.get("event_id"), timestamp=timestamp, now=now,
                  metric=payload.get("metric", config.DEFAULT_METRIC))
    if units == 1 and not payload.get("batch"):
        return record_call(store, customer_id, **kwargs)
    return record_batch(store, customer_id, units, **kwargs)
