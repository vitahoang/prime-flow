from decimal import Decimal

import pytest

from meterly import pricing
from meterly.models import Plan, Tier


def plan(*tiers, base="10.00"):
    return Plan("p", "P", "USD", Decimal(base), [Tier(u, Decimal(p)) for u, p in tiers])


def test_validate_tiers_ok():
    pricing.validate_tiers(plan((100, "0.10"), (None, "0.05")).tiers)


@pytest.mark.parametrize("tiers", [
    [],
    [(None, "0.1"), (100, "0.05")],
    [(100, "0.1"), (50, "0.05"), (None, "0.01")],
    [(100, "0.1")],
    [(100, "-0.1"), (None, "0.1")],
])
def test_validate_tiers_rejects(tiers):
    with pytest.raises(pricing.PricingError):
        pricing.validate_tiers(plan(*tiers).tiers)


def test_tier_for():
    p = plan((100, "0.10"), (1000, "0.05"), (None, "0.01"))
    assert pricing.tier_for(p, 1).unit_price == Decimal("0.10")
    assert pricing.tier_for(p, 100).unit_price == Decimal("0.10")
    assert pricing.tier_for(p, 101).unit_price == Decimal("0.05")
    assert pricing.tier_for(p, 5000).unit_price == Decimal("0.01")


def test_price_units():
    p = plan((100, "0.10"), (None, "0.05"))
    assert pricing.price_units(p, 0) == 0
    assert pricing.price_units(p, 50) == Decimal("5.00")


def test_describe_tiers():
    p = plan((100, "0.10"), (None, "0.05"))
    assert pricing.describe_tiers(p) == ["1-100 : 0.10 per unit", "101+ : 0.05 per unit"]


def test_example_plans_are_valid(store):
    for p in store.plans.values():
        pricing.validate_plan(p)
