"""Exporting entries."""

import csv
import sys
from typing import Optional

from ledger import query, storage
from ledger.formatting import format_amount
from ledger.settings import load_settings

HEADER = ["id", "timestamp", "description", "category", "amount"]


def run(fmt: str, start: Optional[str], end: Optional[str]) -> int:
    settings = load_settings()
    entries = storage.load_entries()
    entries = query.in_range(
        entries,
        query.parse_date(start) if start else None,
        query.parse_date(end) if end else None,
    )
    writer = csv.writer(sys.stdout)
    writer.writerow(HEADER)
    for entry in entries:
        writer.writerow([
            entry.id,
            entry.ts,
            entry.description,
            entry.category,
            format_amount(entry.amount_cents, settings),
        ])
    return 0
