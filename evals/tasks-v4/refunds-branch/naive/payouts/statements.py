"""Merchant statements: every ledger movement plus the resulting balance."""

from __future__ import annotations

from dataclasses import dataclass, field

from payouts import clock, ledger
from payouts.merchants import get_merchant
from payouts.models import LedgerEntry, Merchant
from payouts.money import format_cents, sum_cents
from payouts.store import Store

LABELS = {
    ledger.CHARGE: "Charge",
    ledger.FEE: "Fee",
    ledger.PAYOUT: "Payout",
    ledger.ADJUSTMENT: "Adjustment",
    ledger.REFUND: "Refund",
}

# Order of the per-kind totals under the lines.
SUMMARY_ORDER = (ledger.CHARGE, ledger.FEE, ledger.REFUND, ledger.PAYOUT, ledger.ADJUSTMENT)


@dataclass
class StatementLine:
    date: str
    label: str
    ref: str
    memo: str
    amount_cents: int


@dataclass
class Statement:
    merchant: Merchant
    lines: list[StatementLine] = field(default_factory=list)
    totals: dict[str, int] = field(default_factory=dict)

    @property
    def balance_cents(self) -> int:
        return sum_cents(line.amount_cents for line in self.lines)


def _line(entry: LedgerEntry) -> StatementLine:
    return StatementLine(
        date=clock.date_part(entry.created_at),
        label=LABELS[entry.kind],
        ref=entry.ref,
        memo=entry.memo,
        amount_cents=entry.amount_cents,
    )


def build_statement(store: Store, merchant_id: str) -> Statement:
    merchant = get_merchant(store, merchant_id)
    entries = sorted(ledger.entries_for(store, merchant.id), key=lambda e: (e.created_at, e.id))
    statement = Statement(merchant=merchant, lines=[_line(e) for e in entries])
    for entry in entries:
        statement.totals[entry.kind] = statement.totals.get(entry.kind, 0) + entry.amount_cents
    return statement


def render(statement: Statement) -> str:
    m = statement.merchant
    cur = m.currency
    out = [f"Statement for {m.name} ({m.id}), {cur}", ""]
    if not statement.lines:
        out.append("  (no activity)")
    for line in statement.lines:
        memo = (line.memo[:28] + "...") if len(line.memo) > 31 else line.memo
        out.append(
            f"  {line.date}  {line.label:<11} {line.ref:<9} {memo:<31} {format_cents(line.amount_cents, cur):>12}"
        )
    out.append("")
    for kind in SUMMARY_ORDER:
        if kind in statement.totals:
            out.append(f"  {LABELS[kind] + 's':<13}{format_cents(statement.totals[kind], cur):>12}")
    out.append(f"Balance: {format_cents(statement.balance_cents, cur)}")
    return "\n".join(out)
