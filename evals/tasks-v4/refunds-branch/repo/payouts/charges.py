"""Charging a customer on behalf of a merchant."""

from __future__ import annotations

from payouts import clock, ledger
from payouts.errors import NotFound, ValidationError
from payouts.fees import fee_for
from payouts.gateway import FakeGateway, call_with_retries, new_idempotency_key
from payouts.merchants import get_merchant
from payouts.models import Charge
from payouts.money import format_cents
from payouts.store import Store

TABLE = "charges"
MAX_DESCRIPTION = 200


def create_charge(
    store: Store,
    gateway: FakeGateway,
    merchant_id: str,
    amount_cents: int,
    description: str = "",
) -> Charge:
    """Charge ``amount_cents`` (minor units of the merchant's currency) and credit the merchant, less our fee.

    The gateway call is retried on timeout.
    """
    merchant = get_merchant(store, merchant_id)
    if not merchant.active:
        raise ValidationError(f"merchant {merchant_id} is suspended")
    if not isinstance(amount_cents, int) or amount_cents <= 0:
        raise ValidationError("charge amount must be a positive number of cents")
    description = (description or "").strip()
    if len(description) > MAX_DESCRIPTION:
        raise ValidationError(f"description longer than {MAX_DESCRIPTION} characters")

    key = new_idempotency_key()
    result = call_with_retries(
        lambda: gateway.charge(amount_cents, description, idempotency_key=key)
    )

    fee = fee_for(merchant, amount_cents)
    charge = Charge(
        id=store.next_id("ch"),
        merchant_id=merchant.id,
        amount_cents=amount_cents,
        fee_cents=fee,
        description=description,
        gateway_ref=result["ref"],
        created_at=clock.now_iso(),
        currency=merchant.currency,
    )
    store.insert(TABLE, charge.to_dict())
    ledger.record(store, merchant.id, ledger.CHARGE, amount_cents, ref=charge.id, memo=description)
    if fee:
        ledger.record(store, merchant.id, ledger.FEE, -fee, ref=charge.id, memo="processing fee")
    return charge


def get_charge(store: Store, charge_id: str) -> Charge:
    try:
        return Charge.from_dict(store.get(TABLE, charge_id))
    except NotFound:
        raise NotFound(f"no charge with id {charge_id}") from None


def charges_for(store: Store, merchant_id: str) -> list[Charge]:
    rows = store.find(TABLE, lambda r: r["merchant_id"] == merchant_id)
    return [Charge.from_dict(r) for r in rows]


def summarize(charge: Charge) -> str:
    cur = charge.currency
    return f"{charge.id} {format_cents(charge.amount_cents, cur)} {cur} (fee {format_cents(charge.fee_cents, cur)})"
