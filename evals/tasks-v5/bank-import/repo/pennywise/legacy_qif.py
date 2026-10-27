"""Reader for the QIF files the old GnuCash setup exported.

Kept for reference; nothing calls it any more. The GnuCash data was migrated
by hand in 2023.
"""

from datetime import datetime

from .money import parse_amount


def read_qif(path):
    """Yield dicts with date, amount_cents, payee, memo from a !Type:Bank QIF."""
    entry = {}
    with open(path, encoding="latin-1") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line or line.startswith("!"):
                continue
            code, value = line[0], line[1:].strip()
            if code == "D":
                entry["date"] = datetime.strptime(value.replace("'", "/"), "%d/%m/%Y").date()
            elif code == "T":
                entry["amount_cents"] = parse_amount(value)
            elif code == "P":
                entry["payee"] = value
            elif code == "M":
                entry["memo"] = value
            elif code == "^":
                if entry:
                    yield entry
                entry = {}


def dedupe(entries, existing):
    """Drop entries already in `existing` (a set of (date, amount, payee))."""
    seen = set(existing)
    for e in entries:
        key = (e["date"], e["amount_cents"], e.get("payee", ""))
        if key in seen:
            continue
        seen.add(key)
        yield e


def import_qif(store, account, path):
    existing = {(t.posted, t.amount_cents, t.description)
                for t in store.list_transactions(account_id=account.id)}
    count = 0
    for e in dedupe(read_qif(path), existing):
        store.add_transaction(account.id, e["date"], e["amount_cents"], e.get("payee", ""),
                              note=e.get("memo"), source="qif")
        count += 1
    return count
