"""Exporting entries for spreadsheets."""

import csv
import io
import sys
from datetime import date
from typing import Optional

from ledger import query, storage
from ledger.settings import load_settings

HEADER = ["id", "date", "description", "category", "amount"]


def plain_amount(cents: int) -> str:
    """``-123456`` -> ``-1234.56``: no symbol, no separators."""
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def run(fmt: str, start: Optional[str], end: Optional[str]) -> int:
    settings = load_settings()
    first = date.fromisoformat(start) if start else None
    last = date.fromisoformat(end) if end else None

    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(HEADER)
    for entry in query.active(storage.load_entries()):
        local_day = entry.when.astimezone(settings.tz).date()
        if first is not None and local_day < first:
            continue
        if last is not None and local_day > last:  # --to is inclusive
            continue
        writer.writerow([
            entry.id,
            local_day.isoformat(),
            entry.description,
            entry.category,
            plain_amount(entry.amount_cents),
        ])

    # UTF-8 with a BOM and CRLF rows so Excel on Windows opens it cleanly.
    sys.stdout.buffer.write(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0
