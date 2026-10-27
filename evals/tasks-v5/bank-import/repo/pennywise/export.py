"""Write an account's transactions back out as CSV (for the accountant)."""

import csv
import io

from .money import to_decimal_str

COLUMNS = ["date", "description", "amount", "category", "note"]


def export_csv(store, account, fh=None):
    names = store.category_names()
    out = fh or io.StringIO()
    writer = csv.writer(out)
    writer.writerow(COLUMNS)
    for txn in store.list_transactions(account_id=account.id):
        writer.writerow([
            txn.posted.isoformat(),
            txn.description,
            to_decimal_str(txn.amount_cents),
            names.get(txn.category_id, ""),
            txn.note or "",
        ])
    if fh is None:
        return out.getvalue()
    return None
