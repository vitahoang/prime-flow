"""CSV export of a merchant's ledger, for the finance team's spreadsheet.

Finance asked for this in the spring; it was never hooked up to the CLI
because they ended up reading statements instead.
"""

from __future__ import annotations

import csv
from pathlib import Path

from payouts import ledger
from payouts.money import format_cents
from payouts.store import Store

COLUMNS = ("date", "kind", "ref", "memo", "amount")


def export_ledger_csv(store: Store, merchant_id: str, path: Path | str) -> int:
    entries = sorted(ledger.entries_for(store, merchant_id), key=lambda e: e.created_at)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for e in entries:
            writer.writerow([e.created_at[:10], e.kind, e.ref, e.memo, format_cents(e.amount_cents)])
    return len(entries)


def _legacy_rows(store: Store, merchant_id: str) -> list[list[str]]:
    # Old export format (pre-ledger), kept until finance confirms nobody uses it.
    rows = []
    for charge in store.find("charges", lambda r: r["merchant_id"] == merchant_id):
        rows.append([charge["id"], format_cents(charge["amount_cents"]), charge.get("description", "")])
    return rows
