"""Refunds: giving a customer back some or all of a charge.

Partial refunds are allowed. The merchant's processing fee is not returned
(finance's call), so a refund takes exactly the refunded amount off the
merchant's balance.
"""

from __future__ import annotations

from itertools import groupby
from operator import itemgetter

from payouts import clock, ledger
from payouts.charges import get_charge
from payouts.errors import PayoutsError
from payouts.gateway import FakeGateway, call_with_retries
from payouts.models import Refund
from payouts.store import Store
from payouts.utils import _display, _to_amount

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

    ``amount`` is what the user typed ("12.50") or an int amount in cents.
    """
    charge = get_charge(store, charge_id)
    amount_cents = _to_amount(amount)
    if amount_cents <= 0:
        raise RefundError("refund amount must be positive")
    already = _refunded_by_charge(store, charge.merchant_id).get(charge.id, 0)
    if amount_cents > charge.amount_cents - already:
        raise RefundError(
            f"refund of {_display(amount_cents)} is more than what's left on the charge "
            f"({_display(charge.amount_cents - already)} of {_display(charge.amount_cents)})"
        )
    if reason is not None:
        reason = reason.strip() or None
        if reason and len(reason) > MAX_REASON:
            raise RefundError(f"reason longer than {MAX_REASON} characters")

    result = call_with_retries(lambda: gateway.refund(charge.gateway_ref, amount_cents))

    refund = Refund(
        id=store.next_id("re"),
        charge_id=charge.id,
        merchant_id=charge.merchant_id,
        amount_cents=amount_cents,
        currency=charge.currency,
        gateway_ref=result["ref"],
        created_at=clock.now_iso(),
        reason=reason,
    )
    store.insert(TABLE, refund.to_dict())
    ledger.record(store, charge.merchant_id, ledger.REFUND, -refund.amount_cents, ref=refund.id, memo=reason or "")
    return refund


def refunds_for_charge(store: Store, charge_id: str) -> list[Refund]:
    rows = store.find(TABLE, lambda r: r["charge_id"] == charge_id)
    return [Refund.from_dict(r) for r in rows]


def _refunded_by_charge(store: Store, merchant_id: str) -> dict[str, int]:
    """Total refunded so far on each of a merchant's charges."""
    rows = store.find(TABLE, lambda r: r["merchant_id"] == merchant_id)
    return {
        charge_id: sum(r["amount_cents"] for r in group)
        for charge_id, group in groupby(rows, key=itemgetter("charge_id"))
    }
