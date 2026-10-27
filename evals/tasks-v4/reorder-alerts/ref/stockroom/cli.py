"""Command line: ``python -m stockroom <command> ...``.

Commands:
    stock       stock on hand (chain-wide by default)
    movements   recent stock movements
    po list     purchase orders
    reorder     what each shop needs to order
    report      weekly waste / best-seller reports
    check       sanity-check the data directory
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from typing import List, Optional

from . import __version__, clock, config
from .formatting import fmt_date, fmt_money, fmt_qty, table
from .ledger import chain_totals, filter_movements, on_hand_by_shop, outflow_by_sku
from .models import MovementType, POStatus
from .purchasing import list_orders, order_value, overdue
from .reorder import suggest
from .reports import top_sellers, waste_report
from .store import DataError, Inventory, load
from .validation import check


def _load(args) -> Inventory:
    return load(config.data_dir(args.data))


def _shop_arg(inv: Inventory, code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return inv.shop(code).code  # raises DataError for an unknown shop


def _print_json(data) -> None:
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


# --- stock -------------------------------------------------------------------

def cmd_stock(args) -> int:
    inv = _load(args)
    shop = _shop_arg(inv, args.shop)
    levels = on_hand_by_shop(inv.movements, as_of=clock.today())
    if shop:
        levels = {k: v for k, v in levels.items() if k[0] == shop}

    if args.by_shop or shop:
        keys = sorted(levels, key=lambda k: (config.shop_sort_key(k[0]), k[1]))
        records = [{"shop": s, "sku": sku, "on_hand": levels[(s, sku)]} for s, sku in keys]
    else:
        totals = chain_totals(levels)
        records = [{"shop": "ALL", "sku": sku, "on_hand": qty} for sku, qty in sorted(totals.items())]

    if args.activity:
        since = clock.today() - timedelta(days=args.days)
        for rec in records:
            out = outflow_by_sku(inv.movements, since,
                                 shop=None if rec["shop"] == "ALL" else rec["shop"])
            rec["out"] = out.get(rec["sku"], 0.0)

    if args.json:
        _print_json(records)
        return 0

    headers = ["Shop", "SKU", "Item", "On hand"]
    if args.activity:
        headers.append(f"Out ({args.days}d)")
    rows = []
    for rec in records:
        item = inv.items.get(rec["sku"])
        row = [rec["shop"], rec["sku"], item.name if item else "?",
               fmt_qty(rec["on_hand"], item.unit if item else None)]
        if args.activity:
            row.append(fmt_qty(rec["out"]))
        rows.append(row)
    if not rows:
        print("No stock recorded.")
        return 0
    print(table(headers, rows, align="lllr" + ("r" if args.activity else "")))
    return 0


# --- movements -----------------------------------------------------------------

def cmd_movements(args) -> int:
    inv = _load(args)
    shop = _shop_arg(inv, args.shop)
    since = clock.today() - timedelta(days=args.days)
    types = [MovementType(t) for t in args.type] if args.type else None
    found = filter_movements(inv.movements, shop=shop, sku=args.sku, since=since, types=types)

    if args.json:
        _print_json([
            {"date": m.date.isoformat(), "shop": m.shop, "sku": m.sku,
             "type": m.type.value, "qty": m.qty, "ref": m.ref}
            for m in found
        ])
        return 0
    if not found:
        print(f"No movements in the last {args.days} days.")
        return 0
    rows = [[m.date.isoformat(), m.shop, m.sku, m.type.value,
             fmt_qty(m.signed_qty), m.ref] for m in found]
    print(table(["Date", "Shop", "SKU", "Type", "Qty", "Ref"], rows, align="llllrl"))
    return 0


# --- purchase orders -----------------------------------------------------------

def cmd_po_list(args) -> int:
    inv = _load(args)
    shop = _shop_arg(inv, args.shop)
    status = POStatus(args.status) if args.status else None
    orders = list_orders(inv.purchase_orders, status=status, shop=shop, supplier=args.supplier)
    late = {po.id for po in overdue(orders, clock.today())}

    if args.json:
        _print_json([
            {"id": po.id, "supplier": po.supplier, "shop": po.shop, "status": po.status.value,
             "ordered": po.ordered.isoformat(),
             "expected": po.expected.isoformat() if po.expected else None,
             "lines": [{"sku": l.sku, "qty": l.qty} for l in po.lines]}
            for po in orders
        ])
        return 0
    if not orders:
        print("No purchase orders.")
        return 0
    rows = []
    for po in orders:
        lines = ", ".join(f"{l.sku} x{fmt_qty(l.qty)}" for l in po.lines)
        flag = " LATE" if po.id in late else ""
        rows.append([po.id, po.shop, po.supplier, po.status.value + flag,
                     fmt_date(po.ordered), fmt_date(po.expected),
                     fmt_money(order_value(po, inv.suppliers.get(po.supplier))), lines])
    print(table(["PO", "Shop", "Supplier", "Status", "Ordered", "Expected", "Value", "Lines"],
                rows, align="llllllrl"))
    return 0


# --- reorder -------------------------------------------------------------------

def cmd_reorder(args) -> int:
    inv = _load(args)
    shop = _shop_arg(inv, args.shop)
    lines = suggest(inv, clock.today(), shop=shop)
    if args.json:
        _print_json([line.as_dict() for line in lines])
        return 0
    if not lines:
        print("Nothing to reorder.")
        return 0
    rows = []
    for l in lines:
        unit = inv.items[l.sku].unit
        rows.append([l.shop, l.sku, l.name, fmt_qty(l.on_hand), fmt_qty(l.on_order),
                     f"{l.daily_usage:.1f}", fmt_qty(l.order_qty, unit),
                     f"{l.order_qty // l.case_size} x {l.case_size}", l.supplier])
    print(table(["Shop", "SKU", "Item", "On hand", "On order", "Use/day", "Order", "Cases",
                 "Supplier"], rows, align="lllrrrrrl"))
    return 0


# --- reports -------------------------------------------------------------------

def cmd_report(args) -> int:
    inv = _load(args)
    shop = _shop_arg(inv, args.shop)
    until = clock.today()
    since = until - timedelta(days=args.days - 1)
    if args.kind == "waste":
        lines = waste_report(inv, since, until, shop=shop)
        if not lines:
            print("No waste recorded.")
            return 0
        rows = [[l.shop, l.sku, fmt_qty(l.qty), fmt_money(l.cost),
                 "-" if l.share_of_sales is None else f"{l.share_of_sales:.0%}"] for l in lines]
        print(table(["Shop", "SKU", "Wasted", "Cost", "% of sales"], rows, align="llrrr"))
    else:
        ranked = top_sellers(inv, since, until, shop=shop, limit=args.limit)
        if not ranked:
            print("No sales recorded.")
            return 0
        rows = [[sku, inv.items[sku].name if sku in inv.items else "?", fmt_qty(qty)]
                for sku, qty in ranked]
        print(table(["SKU", "Item", "Sold"], rows, align="llr"))
    return 0


# --- check -----------------------------------------------------------------------

def cmd_check(args) -> int:
    inv = _load(args)
    problems = check(inv)
    for p in problems:
        print(p)
    if problems:
        print(f"{len(problems)} problem(s)")
        return 1
    print("OK")
    return 0


# --- parser ----------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stockroom", description="Stock for the shops.")
    parser.add_argument("--data", help="data directory (default: $STOCKROOM_DATA or ./data)")
    parser.add_argument("--version", action="version", version=f"stockroom {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("stock", help="stock on hand")
    p.add_argument("--shop", help="one shop only (shop code, e.g. MKT)")
    p.add_argument("--by-shop", action="store_true", help="one row per shop instead of chain totals")
    p.add_argument("--activity", action="store_true", help="add an 'out' column")
    p.add_argument("--days", type=int, default=7, help="days of activity (default 7)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_stock)

    p = sub.add_parser("movements", help="recent stock movements")
    p.add_argument("--shop")
    p.add_argument("--sku")
    p.add_argument("--type", action="append", choices=[t.value for t in MovementType])
    p.add_argument("--days", type=int, default=7, help="how far back (default 7)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_movements)

    p = sub.add_parser("po", help="purchase orders")
    po_sub = p.add_subparsers(dest="po_command", required=True)
    pl = po_sub.add_parser("list", help="list purchase orders")
    pl.add_argument("--status", choices=[s.value for s in POStatus])
    pl.add_argument("--shop")
    pl.add_argument("--supplier")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_po_list)

    p = sub.add_parser("reorder", help="what needs ordering, per shop")
    p.add_argument("--shop", help="one shop only (shop code)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_reorder)

    p = sub.add_parser("report", help="weekly reports")
    p.add_argument("kind", choices=["waste", "top"])
    p.add_argument("--shop")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("check", help="sanity-check the data")
    p.set_defaults(func=cmd_check)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DataError as exc:
        print(f"stockroom: {exc}", file=sys.stderr)
        return 2
