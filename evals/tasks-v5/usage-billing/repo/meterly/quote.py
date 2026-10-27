"""Price estimates for the pricing page ("what would 50k calls a month cost?").

Same maths as billing, so the pricing page and the invoice always agree.
"""

from decimal import Decimal

from . import pricing
from .money import format_major, round_half_up
from .store import Store


def estimate(store: Store, plan_id: str, monthly_units: int) -> dict:
    """Estimated monthly cost of ``plan_id`` at ``monthly_units`` units, before tax."""
    plan = store.plan(plan_id)
    usage = pricing.price_units(plan, monthly_units)
    total = plan.base_fee + usage
    if total < plan.minimum_charge:
        total = plan.minimum_charge
    return {
        "plan": plan.id,
        "currency": plan.currency,
        "units": monthly_units,
        "base_fee": plan.base_fee,
        "usage": round_half_up(usage),
        "total": round_half_up(total),
    }


def compare(store: Store, monthly_units: int, currency: str = None) -> list:
    """Estimates for every active plan, cheapest first."""
    rows = []
    for plan in store.plans.values():
        if not plan.active:
            continue
        if currency and plan.currency != currency.upper():
            continue
        rows.append(estimate(store, plan.id, monthly_units))
    rows.sort(key=lambda r: r["total"])
    return rows


def render(row: dict) -> str:
    cur = row["currency"]
    return (f"{row['plan']:<12} {row['units']:>10,} units  "
            f"base {format_major(Decimal(row['base_fee']), cur):>10}  "
            f"usage {format_major(Decimal(row['usage']), cur):>10}  "
            f"total {format_major(Decimal(row['total']), cur):>10}")
