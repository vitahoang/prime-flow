"""Merchant accounts."""

from __future__ import annotations

from payouts import clock, config, money
from payouts.errors import NotFound, ValidationError
from payouts.models import ACTIVE, SUSPENDED, Merchant
from payouts.store import Store

TABLE = "merchants"
MAX_FEE_BPS = 2_000  # 20%; anything above is certainly a typo


def create_merchant(
    store: Store,
    name: str,
    *,
    fee_bps: int = config.DEFAULT_FEE_BPS,
    fee_fixed_cents: int = config.DEFAULT_FEE_FIXED_CENTS,
    email: str | None = None,
    currency: str = money.DEFAULT_CURRENCY,
) -> Merchant:
    name = (name or "").strip()
    if not name:
        raise ValidationError("merchant name is required")
    if not 0 <= fee_bps <= MAX_FEE_BPS:
        raise ValidationError(f"fee_bps must be between 0 and {MAX_FEE_BPS}")
    currency = (currency or "").upper()
    money.exponent(currency)  # raises for currencies we don't settle in
    if fee_fixed_cents < 0:
        raise ValidationError("fee_fixed_cents must not be negative")
    if any(m["name"].lower() == name.lower() for m in store.load(TABLE)):
        raise ValidationError(f"a merchant called {name!r} already exists")
    merchant = Merchant(
        id=store.next_id("m"),
        name=name,
        fee_bps=fee_bps,
        fee_fixed_cents=fee_fixed_cents,
        created_at=clock.now_iso(),
        email=email,
        currency=currency,
    )
    store.insert(TABLE, merchant.to_dict())
    return merchant


def get_merchant(store: Store, merchant_id: str) -> Merchant:
    try:
        return Merchant.from_dict(store.get(TABLE, merchant_id))
    except NotFound:
        raise NotFound(f"no merchant with id {merchant_id}") from None


def list_merchants(store: Store, *, include_suspended: bool = True) -> list[Merchant]:
    merchants = [Merchant.from_dict(row) for row in store.load(TABLE)]
    if not include_suspended:
        merchants = [m for m in merchants if m.active]
    return sorted(merchants, key=lambda m: m.id)


def suspend_merchant(store: Store, merchant_id: str) -> Merchant:
    get_merchant(store, merchant_id)
    return Merchant.from_dict(store.update(TABLE, merchant_id, status=SUSPENDED))


def reactivate_merchant(store: Store, merchant_id: str) -> Merchant:
    get_merchant(store, merchant_id)
    return Merchant.from_dict(store.update(TABLE, merchant_id, status=ACTIVE))
