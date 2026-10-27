"""Refunds: giving a customer back some or all of a charge.

Partial refunds are allowed, but the refunds on a charge never add up to
more than the charge, and a voided charge can't be refunded (the customer
was never billed). A refund after the money was paid out still goes
through; the merchant's balance goes below zero and the shortfall comes off
their next payout (the statement shows it as carried). The merchant's
processing fee is not returned (finance's call), so a refund takes exactly
the refunded amount off the merchant's balance.
"""

from __future__ import annotations

from payouts import clock, ledger
from payouts.charges import get_charge
from payouts.errors import MoneyError, PayoutsError
from payouts.gateway import FakeGateway, call_with_retries, new_idempotency_key
from payouts.models import SUCCEEDED, Refund
from payouts.money import format_cents, parse_amount
from payouts.store import Store

TABLE = "refunds"
MAX_REASON = 200


class RefundError(PayoutsError):
    """A refund was refused."""


def create_refund(
    store: Store,
    gateway: FakeGateway,
    charge_id: str,
    amount: str | int,
    reason: str | None = None,
) -> Refund:
    """Refund ``amount`` of charge ``charge_id`` back to the customer.

    ``amount`` is what the user typed, in the charge's currency ("12.50", or
    "500" for yen), or an int in minor units. The gateway call is retried on
    timeout with one idempotency key for all attempts, so a timed-out refund
    that actually went through is not paid out twice.
    """
    charge = get_charge(store, charge_id)
    cur = charge.currency
    if charge.status != SUCCEEDED:
        raise RefundError(f"charge {charge.id} is {charge.status} and can't be refunded")
    if isinstance(amount, int) and not isinstance(amount, bool):
        amount_cents = amount
    else:
        try:
            amount_cents = parse_amount(amount, cur)
        except MoneyError as exc:
            raise RefundError(f"bad refund amount: {exc}") from None
    if amount_cents <= 0:
        raise RefundError("refund amount must be positive")
    remaining = charge.amount_cents - refunded_total(store, charge.id)
    if remaining <= 0:
        raise RefundError(f"charge {charge.id} is already fully refunded")
    if amount_cents > remaining:
        raise RefundError(
            f"refund of {format_cents(amount_cents, cur)} {cur} is more than what is left to refund on "
            f"{charge.id} ({format_cents(remaining, cur)} of {format_cents(charge.amount_cents, cur)})"
        )
    if reason is not None:
        reason = reason.strip() or None
        if reason and len(reason) > MAX_REASON:
            raise RefundError(f"reason longer than {MAX_REASON} characters")

    key = new_idempotency_key()
    result = call_with_retries(
        lambda: gateway.refund(charge.gateway_ref, amount_cents, idempotency_key=key)
    )

    refund = Refund(
        id=store.next_id("re"),
        charge_id=charge.id,
        merchant_id=charge.merchant_id,
        amount_cents=amount_cents,
        currency=cur,
        gateway_ref=result["ref"],
        created_at=clock.now_iso(),
        reason=reason,
    )
    store.insert(TABLE, refund.to_dict())
    ledger.record(store, charge.merchant_id, ledger.REFUND, -amount_cents, ref=refund.id, memo=reason or "")
    return refund


def refunds_for_charge(store: Store, charge_id: str) -> list[Refund]:
    rows = store.find(TABLE, lambda r: r["charge_id"] == charge_id)
    return [Refund.from_dict(r) for r in rows]


def refunded_total(store: Store, charge_id: str) -> int:
    """Amount refunded so far on a charge, in minor units."""
    return sum(r.amount_cents for r in refunds_for_charge(store, charge_id))
