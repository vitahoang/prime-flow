"""Internal reports for support and for the monthly founder email."""

from datetime import date
from decimal import Decimal
from typing import List

from . import config, periods, pricing, usage
from .money import round_half_up
from .store import Store


def activity(store: Store, start: date, end: date) -> List[dict]:
    """API calls per customer in [start, end), busiest first. Used by support."""
    rows = []
    for customer in store.customers.values():
        lo, hi = periods.period_bounds_utc(start, end, customer.timezone)
        events = usage.events_for(store, customer.id, lo, hi)
        rows.append({
            "customer": customer.id,
            "name": customer.name,
            "plan": customer.plan_id,
            "tags": list(customer.tags),
            "calls": usage.count_calls(events),
            "last_seen": usage.last_seen(store, customer.id),
        })
    rows.sort(key=lambda r: r["calls"], reverse=True)
    return rows


def inactive(store: Store, start: date, end: date) -> List[str]:
    """Customers with no calls at all in the period."""
    return [r["customer"] for r in activity(store, start, end) if r["calls"] == 0]


def plan_mix(store: Store) -> dict:
    mix = {}
    for customer in store.customers.values():
        mix[customer.plan_id] = mix.get(customer.plan_id, 0) + 1
    return dict(sorted(mix.items()))


def legacy_mrr(store: Store, start: date, end: date) -> Decimal:
    """Rough MRR incl. VAT, from the 2025 spreadsheet days. Superseded by the
    finance dashboard; kept until Dana confirms nothing reads it."""
    total = Decimal("0")
    for row in activity(store, start, end):
        plan = store.plan(row["plan"])
        total += plan.base_fee + pricing.price_units(plan, row["calls"])
    return round_half_up(total * (1 + config.VAT_RATE))
