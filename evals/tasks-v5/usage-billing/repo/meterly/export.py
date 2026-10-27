"""CSV export of usage events, for customers who ask for a raw dump."""

import csv
from datetime import date
from pathlib import Path

from . import periods, usage
from .models import format_ts
from .store import Store

FIELDS = ["event_id", "timestamp", "received_at", "units", "metric", "source"]


def export_events(store: Store, customer_id: str, start: date, end: date, path: Path) -> int:
    """Write the customer's events in local [start, end) to ``path``. Returns rows written."""
    customer = store.customer(customer_id)
    lo, hi = periods.period_bounds_utc(start, end, customer.timezone)
    events = usage.events_for(store, customer_id, lo, hi)
    with Path(path).open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(FIELDS)
        for e in events:
            writer.writerow([e.event_id, format_ts(e.timestamp), format_ts(e.received_at),
                             e.units, e.metric, e.source])
    return len(events)
