"""Command line: python -m invoicer <command> ...

Commands:
    list                       all invoices with status and balance
    show INVOICE_ID [--html]   one invoice, as text (or HTML)
    customers                  all customers
    statement CUSTOMER_ID      a customer's statement with aging
    reminders [--on DATE]      payment reminders scheduled from today
    reminders --send           today's reminders, recorded as sent
    overdue                    charge late fees, list overdue invoices

The daily run is `overdue` then `reminders --send`.

The data directory comes from INVOICER_DATA_DIR (default: ./data in the
project). INVOICER_NOW pins the current time, e.g. INVOICER_NOW=2026-10-11T09:00:00Z.
"""

import argparse
import sys
from datetime import date

from . import billing, clock, money, reminders, render, statement, utils
from .store import DataError, Store


def _store(args) -> Store:
    return Store(args.data_dir) if args.data_dir else Store()


def cmd_list(args) -> int:
    store = _store(args)
    now = clock.now()
    rows = [("Invoice", "Customer", "Due", "Status", "Balance")]
    for inv in store.all_invoices():
        cust = store.customer_for(inv)
        rows.append(
            (
                inv.id,
                cust.name,
                utils.format_date(billing.due_date(inv, cust), "iso"),
                billing.status(inv, cust, store.payments, now),
                money.format_money(billing.balance(inv, store.payments), inv.currency),
            )
        )
    print("\n".join(utils.table(rows, [9, 26, 10, 8, 16], ["left", "left", "left", "left", "right"])))
    return 0


def cmd_show(args) -> int:
    store = _store(args)
    inv = store.invoice(args.invoice_id)
    if inv is None:
        print(f"No invoice {args.invoice_id}", file=sys.stderr)
        return 2
    cust = store.customer_for(inv)
    payments = store.payments_for(inv.id)
    fees = store.fees_for(inv.id)
    if args.html:
        sys.stdout.write(render.render_html(inv, cust, payments, clock.now(), fees))
    else:
        sys.stdout.write(render.render_text(inv, cust, payments, clock.now(), fees))
    return 0


def cmd_customers(args) -> int:
    store = _store(args)
    rows = [("ID", "Name", "Time zone", "Currency")]
    for c in sorted(store.customers.values(), key=lambda c: c.id):
        rows.append((c.id, c.name, c.timezone, c.currency))
    print("\n".join(utils.table(rows, [6, 28, 22, 8])))
    return 0


def cmd_statement(args) -> int:
    store = _store(args)
    cust = store.customer(args.customer_id)
    if cust is None:
        print(f"No customer {args.customer_id}", file=sys.stderr)
        return 2
    sys.stdout.write(statement.render_statement(store, cust, clock.now()))
    return 0


def cmd_reminders(args) -> int:
    store = _store(args)
    if args.send:
        sent = reminders.send_due(store, clock.now())
        if not sent:
            print("No reminders to send today.")
        for r in sent:
            print("sent  " + reminders.format_reminder(r))
        return 0
    on = date.fromisoformat(args.on) if args.on else None
    items = reminders.upcoming(store, clock.now(), on=on)
    if not items:
        print("No reminders scheduled.")
        return 0
    for r in items:
        print(reminders.format_reminder(r))
    return 0


def cmd_overdue(args) -> int:
    store = _store(args)
    now = clock.now()
    billing.charge_late_fees(store, now)
    found = billing.overdue_invoices(store, now)
    if not found:
        print("No overdue invoices.")
        return 0
    for inv, cust in found:
        due = billing.due_date(inv, cust)
        late = billing.days_overdue(inv, cust, now)
        bal = billing.balance(inv, store.payments)
        fee = billing.late_fee(inv, cust, store.payments, now, store.fees)
        print(
            f"{inv.id}  {cust.name}  due {due.isoformat()}  {utils.plural(late, 'day')} late  "
            f"balance {money.format_money(bal, inv.currency)}  late fee {money.format_money(fee, inv.currency)}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="invoicer", description="Hollis & Rye invoicing")
    p.add_argument("--data-dir", help="data directory (default: $INVOICER_DATA_DIR or ./data)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="all invoices").set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one invoice")
    s.add_argument("invoice_id")
    s.add_argument("--html", action="store_true", help="print HTML instead of text")
    s.set_defaults(func=cmd_show)

    sub.add_parser("customers", help="all customers").set_defaults(func=cmd_customers)

    s = sub.add_parser("statement", help="customer statement")
    s.add_argument("customer_id")
    s.set_defaults(func=cmd_statement)

    s = sub.add_parser("reminders", help="scheduled payment reminders")
    s.add_argument("--on", metavar="YYYY-MM-DD", help="only reminders to send on this date")
    s.add_argument("--send", action="store_true", help="list today's reminders and record them as sent")
    s.set_defaults(func=cmd_reminders)

    sub.add_parser("overdue", help="charge late fees and list overdue invoices").set_defaults(func=cmd_overdue)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except DataError as exc:
        print(f"data error: {exc}", file=sys.stderr)
        return 1
