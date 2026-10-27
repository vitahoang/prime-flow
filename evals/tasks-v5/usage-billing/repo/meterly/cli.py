"""Command line: python -m meterly [--data DIR] <command> ..."""

import argparse
import sys
from datetime import date

from . import periods, pricing, quote, reports, store as store_mod, subscriptions, tax
from .money import format_major


def _parse_month(text: str):
    year, month = text.split("-")
    return periods.month_period(int(year), int(month))


def cmd_customers(st, args):
    for c in sorted(st.customers.values(), key=lambda c: c.id):
        print(f"{c.id:<12} {c.name:<28} {c.country:<3} {c.currency:<4} {c.plan_id:<12} {c.timezone}  {",".join(c.tags)}")
    return 0


def cmd_plans(st, args):
    for p in sorted(st.plans.values(), key=lambda p: p.id):
        flag = "" if p.active else " (retired)"
        print(f"{p.id}{flag}: {p.name}, base {format_major(p.base_fee, p.currency)}")
        if p.free_units:
            print(f"    first {p.free_units:,} units included")
        if p.minimum_charge:
            print(f"    minimum {format_major(p.minimum_charge, p.currency)}")
        for row in pricing.describe_tiers(p):
            print(f"    {row}")
    return 0


def cmd_quote(st, args):
    rows = [quote.estimate(st, args.plan, args.units)] if args.plan else quote.compare(st, args.units, args.currency)
    for row in rows:
        print(quote.render(row))
    return 0


def cmd_activity(st, args):
    start, end = _parse_month(args.month) if args.month else periods.previous_month(date.today())
    for row in reports.activity(st, start, end):
        print(f"{row['customer']:<12} {row['calls']:>10,} calls  {row['plan']}")
    return 0


def cmd_history(st, args):
    for sub in subscriptions.history(st, args.customer):
        print(f"{sub.started_at.isoformat()}  {sub.plan_id}")
    return 0


def cmd_tax(st, args):
    c = st.customer(args.customer)
    print(f"{c.id}: {c.country or '??'} {tax.describe(c.country)}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="meterly")
    p.add_argument("--data", help="data directory (default $METERLY_DATA)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("customers").set_defaults(func=cmd_customers)
    sub.add_parser("plans").set_defaults(func=cmd_plans)
    q = sub.add_parser("quote")
    q.add_argument("units", type=int)
    q.add_argument("--plan")
    q.add_argument("--currency")
    q.set_defaults(func=cmd_quote)
    a = sub.add_parser("activity")
    a.add_argument("--month", help="YYYY-MM (default: last month)")
    a.set_defaults(func=cmd_activity)
    h = sub.add_parser("history")
    h.add_argument("customer")
    h.set_defaults(func=cmd_history)
    t = sub.add_parser("tax")
    t.add_argument("customer")
    t.set_defaults(func=cmd_tax)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    st = store_mod.load(args.data)
    try:
        return args.func(st, args)
    except store_mod.StoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
