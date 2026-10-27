"""The merchant ledger.

Every movement of a merchant's money is one ledger entry with a signed
amount in cents: positive is money we owe the merchant, negative is money
taken out (fees, refunds, payouts). A merchant's balance is the sum of their entries.
"""

from __future__ import annotations

from payouts import clock
from payouts.errors import ValidationError
from payouts.models import LedgerEntry
from payouts.money import sum_cents
from payouts.store import Store

TABLE = "ledger"

CHARGE = "charge"
FEE = "fee"
PAYOUT = "payout"
ADJUSTMENT = "adjustment"
REFUND = "refund"

KINDS = (CHARGE, FEE, PAYOUT, ADJUSTMENT, REFUND)

# Which way each kind is allowed to move money. Adjustments go either way.
SIGNS = {CHARGE: 1, FEE: -1, PAYOUT: -1, REFUND: -1}


def record(
    store: Store,
    merchant_id: str,
    kind: str,
    amount_cents: int,
    *,
    ref: str,
    memo: str = "",
) -> LedgerEntry:
    if kind not in KINDS:
        raise ValidationError(f"unknown ledger kind {kind!r}")
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
        raise ValidationError("ledger amounts must be int cents")
    if amount_cents == 0:
        raise ValidationError("ledger entries must move money")
    sign = SIGNS.get(kind)
    if sign is not None and (amount_cents > 0) != (sign > 0):
        raise ValidationError(f"{kind} entries must be {'positive' if sign > 0 else 'negative'}")
    entry = LedgerEntry(
        id=store.next_id("le"),
        merchant_id=merchant_id,
        kind=kind,
        amount_cents=amount_cents,
        ref=ref,
        memo=memo,
        created_at=clock.now_iso(),
    )
    store.insert(TABLE, entry.to_dict())
    return entry


def entries_for(store: Store, merchant_id: str) -> list[LedgerEntry]:
    rows = store.find(TABLE, lambda r: r["merchant_id"] == merchant_id)
    return [LedgerEntry.from_dict(r) for r in rows]


def balance(store: Store, merchant_id: str) -> int:
    return sum_cents(e.amount_cents for e in entries_for(store, merchant_id))


def totals_by_kind(store: Store, merchant_id: str) -> dict[str, int]:
    totals: dict[str, int] = {}
    for entry in entries_for(store, merchant_id):
        totals[entry.kind] = totals.get(entry.kind, 0) + entry.amount_cents
    return totals
