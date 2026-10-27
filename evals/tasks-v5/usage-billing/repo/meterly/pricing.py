"""Plan price tables.

A plan has a monthly base fee and a list of per-unit tiers, lowest first:

    tiers: [{"up_to": 10000, "unit_price": "0.0100"},
            {"up_to": 100000, "unit_price": "0.0060"},
            {"up_to": null, "unit_price": "0.0030"}]
"""

from decimal import Decimal
from typing import List

from .models import Plan, Tier


class PricingError(ValueError):
    pass


def validate_tiers(tiers: List[Tier]) -> None:
    """Tiers must be ascending, and only the last may be open-ended."""
    if not tiers:
        raise PricingError("a plan needs at least one tier")
    last = 0
    for i, tier in enumerate(tiers):
        if tier.unit_price < 0:
            raise PricingError(f"tier {i}: negative price")
        if tier.up_to is None:
            if i != len(tiers) - 1:
                raise PricingError(f"tier {i}: only the last tier can be open-ended")
            continue
        if tier.up_to <= last:
            raise PricingError(f"tier {i}: up_to must be above {last}")
        last = tier.up_to
    if tiers[-1].up_to is not None:
        raise PricingError("the last tier must be open-ended (up_to: null)")


def validate_plan(plan: Plan) -> None:
    validate_tiers(plan.tiers)
    if plan.base_fee < 0:
        raise PricingError("negative base fee")
    if plan.free_units < 0:
        raise PricingError("negative free_units")
    if plan.minimum_charge < 0:
        raise PricingError("negative minimum_charge")


def tier_for(plan: Plan, units: int) -> Tier:
    """The tier a month with ``units`` units falls into."""
    for tier in plan.tiers:
        if tier.up_to is None or units <= tier.up_to:
            return tier
    return plan.tiers[-1]


def unit_price_for(plan: Plan, units: int) -> Decimal:
    """Per-unit price for a month with ``units`` units."""
    return tier_for(plan, units).unit_price


def price_units(plan: Plan, units: int) -> Decimal:
    """Usage charge for ``units`` units in a month, in major units."""
    if units <= 0:
        return Decimal("0")
    return unit_price_for(plan, units) * units


def describe_tiers(plan: Plan) -> List[str]:
    """Human-readable rows for the pricing page and the CLI."""
    rows = []
    start = 1
    for tier in plan.tiers:
        if tier.up_to is None:
            rows.append(f"{start:,}+ : {tier.unit_price} per unit")
        else:
            rows.append(f"{start:,}-{tier.up_to:,} : {tier.unit_price} per unit")
            start = tier.up_to + 1
    return rows
