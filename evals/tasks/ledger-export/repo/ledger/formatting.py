"""Turning entries into text for the terminal."""

from decimal import Decimal
from typing import List

from ledger.models import Entry
from ledger.settings import Settings


def format_amount(cents: int, settings: Settings) -> str:
    """``-123456`` -> ``-$1,234.56``."""
    sign = "-" if cents < 0 else ""
    value = Decimal(abs(cents)) / 100
    return f"{sign}{settings.currency_symbol}{value:,.2f}"


def format_date(entry: Entry, settings: Settings) -> str:
    """The entry's date in the user's timezone and date format."""
    return entry.when.astimezone(settings.tz).strftime(settings.date_format)


def format_entry(entry: Entry, settings: Settings) -> str:
    marker = " [archived]" if entry.archived else ""
    return (
        f"{entry.id:>4}  {format_date(entry, settings)}  "
        f"{format_amount(entry.amount_cents, settings):>12}  "
        f"{entry.category:<14} {entry.description}{marker}"
    )


def format_table(entries: List[Entry], settings: Settings) -> str:
    if not entries:
        return "No entries."
    return "\n".join(format_entry(e, settings) for e in entries)
