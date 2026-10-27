"""Import a bank's CSV export into an account."""

import csv
from dataclasses import dataclass

from .bank_profiles import get_profile
from .dates import parse_date
from .errors import InvalidInput
from .money import parse_amount


@dataclass
class ImportResult:
    read: int
    added: int
    skipped: int


def _amount(row, profile):
    if profile.amount_column:
        return parse_amount(row[profile.amount_column], profile.decimal)
    paid_in = (row.get(profile.paid_in_column) or "").strip()
    paid_out = (row.get(profile.paid_out_column) or "").strip()
    cents = parse_amount(paid_in, profile.decimal) if paid_in else 0
    if paid_out:
        cents -= parse_amount(paid_out, profile.decimal)
    return cents


def import_file(store, account, path):
    if account.bank == "manual":
        raise InvalidInput(f"account {account.name!r} has no bank profile")
    profile = get_profile(account.bank)
    # Exports overlap: anything on or before the last entry is already in.
    last = store.last_transaction_date(account.id)
    read = added = 0
    with open(path, encoding=profile.encoding, newline="") as fh:
        reader = csv.DictReader(fh, delimiter=profile.delimiter)
        missing = profile.missing_columns(reader.fieldnames or [])
        if missing:
            raise InvalidInput(f"missing columns: {', '.join(missing)}")
        for row in reader:
            read += 1
            posted = parse_date(row[profile.date_column], profile.date_format)
            if last is not None and posted <= last:
                continue
            store.add_transaction(account.id, posted, _amount(row, profile),
                                  row[profile.description_column], source="import")
            added += 1
    return ImportResult(read=read, added=added, skipped=read - added)
