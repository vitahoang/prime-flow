"""Command-line interface: ``python -m ledger <command> ...``."""

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from ledger import query, storage
from ledger.formatting import format_amount, format_table
from ledger.models import Entry, format_ts
from ledger.settings import load_settings


def _parse_amount(value: str) -> int:
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}")
    return int((amount * 100).quantize(Decimal("1")))


def _parse_when(value: str) -> str:
    """Accept ``YYYY-MM-DD`` or ``YYYY-MM-DDTHH:MM`` in the user's timezone."""
    settings = load_settings()
    try:
        local = datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date: {value!r}")
    if local.tzinfo is None:
        local = local.replace(tzinfo=settings.tz)
    return format_ts(local)


def cmd_add(args: argparse.Namespace) -> int:
    entries = storage.load_entries()
    ts = args.when or format_ts(datetime.now(timezone.utc))
    entry = Entry(
        id=storage.next_id(entries),
        ts=ts,
        description=args.description,
        amount_cents=args.amount,
        category=args.category,
    )
    entries.append(entry)
    storage.save_entries(entries)
    print(f"Added entry {entry.id}.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    entries = storage.load_entries()
    if args.category:
        entries = query.by_category(entries, args.category)
    print(format_table(entries, settings))
    return 0


def cmd_balance(args: argparse.Namespace) -> int:
    settings = load_settings()
    entries = query.active(storage.load_entries())
    start = query.parse_date(args.start) if args.start else None
    end = query.parse_date(args.end) if args.end else None
    entries = query.in_range(entries, start, end)
    print(format_amount(query.total_cents(entries), settings))
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    entries = storage.load_entries()
    entry = storage.find_entry(entries, args.id)
    if entry is None:
        print(f"No entry with id {args.id}.", file=sys.stderr)
        return 1
    entry.archived = not args.undo
    storage.save_entries(entries)
    state = "Unarchived" if args.undo else "Archived"
    print(f"{state} entry {entry.id}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add", help="record an income (+) or expense (-)")
    p.add_argument("amount", type=_parse_amount, help="e.g. 1250.00 or -42.10")
    p.add_argument("description")
    p.add_argument("--category", default="uncategorized")
    p.add_argument("--when", type=_parse_when, help="local date/time, default now")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="show entries")
    p.add_argument("--category")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("balance", help="sum of active entries")
    p.add_argument("--from", dest="start", metavar="DATE")
    p.add_argument("--to", dest="end", metavar="DATE")
    p.set_defaults(func=cmd_balance)

    p = sub.add_parser("archive", help="hide an entry from balances")
    p.add_argument("id", type=int)
    p.add_argument("--undo", action="store_true", help="unarchive instead")
    p.set_defaults(func=cmd_archive)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
