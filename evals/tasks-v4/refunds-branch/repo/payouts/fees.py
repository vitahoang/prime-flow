"""Marketplace fees charged to merchants."""

from __future__ import annotations

from payouts.models import Merchant
from payouts.money import apply_bps


def fee_for(merchant: Merchant, amount_cents: int) -> int:
    """Percentage plus fixed fee on a charge, never more than the charge itself."""
    fee = apply_bps(amount_cents, merchant.fee_bps) + merchant.fee_fixed_cents
    return min(fee, amount_cents)


def describe_pricing(merchant: Merchant) -> str:
    pct = merchant.fee_bps / 100
    return f"{pct:g}% + {merchant.fee_fixed_cents}c"
