"""Paying a merchant's balance out to their bank account."""

from __future__ import annotations

from payouts import clock, ledger
from payouts.errors import InsufficientFunds, ValidationError
from payouts.gateway import FakeGateway, call_with_retries, new_idempotency_key
from payouts.merchants import get_merchant
from payouts.models import Payout
from payouts.money import format_cents
from payouts.store import Store

TABLE = "payouts"
MIN_PAYOUT_CENTS = 100  # $1.00, or 100 yen


def create_payout(
    store: Store,
    gateway: FakeGateway,
    merchant_id: str,
    amount_cents: int | None = None,
) -> Payout:
    """Pay out ``amount_cents`` (default: the whole balance)."""
    merchant = get_merchant(store, merchant_id)
    available = ledger.balance(store, merchant.id)
    if amount_cents is None:
        amount_cents = available
    if amount_cents < MIN_PAYOUT_CENTS:
        raise ValidationError(f"payouts must be at least {format_cents(MIN_PAYOUT_CENTS, merchant.currency)}")
    if amount_cents > available:
        raise InsufficientFunds(
            f"balance is {format_cents(available, merchant.currency)}, "
            f"cannot pay out {format_cents(amount_cents, merchant.currency)}"
        )

    key = new_idempotency_key()
    result = call_with_retries(
        lambda: gateway.payout(merchant.id, amount_cents, idempotency_key=key)
    )
    payout = Payout(
        id=store.next_id("po"),
        merchant_id=merchant.id,
        amount_cents=amount_cents,
        gateway_ref=result["ref"],
        created_at=clock.now_iso(),
    )
    store.insert(TABLE, payout.to_dict())
    ledger.record(store, merchant.id, ledger.PAYOUT, -amount_cents, ref=payout.id, memo="bank transfer")
    return payout
