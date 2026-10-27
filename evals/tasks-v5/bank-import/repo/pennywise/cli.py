"""Command-line interface: ``python -m pennywise <command> ...``."""

import argparse
import sys

from . import budget as budget_mod
from . import config, reports, rules
from .bank_profiles import BANKS
from .dates import parse_iso, parse_month
from .errors import PennywiseError
from .export import export_csv
from .formatting import dumps, table, transaction_dict, transactions_table
from .models import CATEGORY_KINDS, RULE_MATCHES
from .money import format_cents, parse_amount
from .store import Store


def _store(args):
    return Store.open(config.db_path(args.db))


# --- accounts ---------------------------------------------------------------

def cmd_accounts_add(args):
    store = _store(args)
    opened = parse_iso(args.opened) if args.opened else None
    currency = args.currency or config.DEFAULT_CURRENCY
    account = store.add_account(args.name, bank=args.bank, currency=currency, opened=opened)
    print(f"added account {account.name} ({account.bank}, {account.currency})")


def cmd_accounts_list(args):
    store = _store(args)
    accounts = store.list_accounts(include_closed=args.all)
    if args.json:
        print(dumps([{"name": a.name, "bank": a.bank, "currency": a.currency,
                      "balance_cents": store.balance(a.id)} for a in accounts]))
        return
    rows = [[a.name, a.bank, a.currency, format_cents(store.balance(a.id), a.currency)]
            for a in accounts]
    print(table(["account", "bank", "currency", "balance"], rows, "lllr"))


def cmd_accounts_show(args):
    store = _store(args)
    a = store.get_account(args.name)
    last = store.last_transaction_date(a.id)
    print(f"{a.name}")
    print(f"  bank:         {a.bank}")
    print(f"  currency:     {a.currency}")
    print(f"  balance:      {format_cents(store.balance(a.id), a.currency)}")
    print(f"  transactions: {store.count_transactions(a.id)}")
    print(f"  last entry:   {last.isoformat() if last else '-'}")


def cmd_accounts_close(args):
    store = _store(args)
    store.close_account(args.name, on=config.today())
    print(f"closed {args.name}")


# --- transactions -----------------------------------------------------------

def cmd_txn_add(args):
    store = _store(args)
    account = store.get_account(args.account)
    category_id = store.get_category(args.category).id if args.category else None
    txn_id = store.add_transaction(
        account.id, parse_iso(args.date), parse_amount(args.amount), args.desc,
        category_id=category_id, note=args.note,
    )
    print(f"added transaction {txn_id}")


def cmd_txn_list(args):
    store = _store(args)
    account_id = store.get_account(args.account).id if args.account else None
    start = end = None
    if args.month:
        from .dates import month_bounds
        start, end = month_bounds(*parse_month(args.month))
    category_id = store.get_category(args.category).id if args.category else None
    txns = store.list_transactions(account_id=account_id, start=start, end=end,
                                   category_id=category_id,
                                   uncategorized=args.uncategorized, limit=args.limit)
    accounts = {a.id: a.name for a in store.list_accounts(include_closed=True)}
    categories = store.category_names()
    if args.json:
        print(dumps([transaction_dict(t, accounts.get(t.account_id), categories) for t in txns]))
    else:
        print(transactions_table(txns, accounts, categories))


def cmd_txn_categorize(args):
    store = _store(args)
    category = store.get_category(args.category)
    store.set_category(args.id, category.id)
    print(f"transaction {args.id} -> {category.name}")


def cmd_txn_delete(args):
    store = _store(args)
    store.delete_transaction(args.id)
    print(f"deleted transaction {args.id}")


# --- categories and rules -----------------------------------------------------

def cmd_categories_add(args):
    store = _store(args)
    cat = store.add_category(args.name, kind=args.kind, parent=args.parent)
    print(f"added category {cat.name} ({cat.kind})")


def cmd_categories_list(args):
    store = _store(args)
    cats = store.list_categories()
    names = {c.id: c.name for c in cats}
    print(table(["category", "kind", "parent"],
                [[c.name, c.kind, names.get(c.parent_id, "")] for c in cats]))


def cmd_rules_add(args):
    store = _store(args)
    category = store.ensure_category(args.category)
    account_id = store.get_account(args.account).id if args.account else None
    rule_id = store.add_rule(args.pattern, category.id, match=args.match,
                             priority=args.priority, account_id=account_id, sign=args.sign)
    print(f"added rule {rule_id}: {args.match} {args.pattern!r} -> {category.name}")


def cmd_rules_list(args):
    store = _store(args)
    names = store.category_names()
    rows = [[r.id, r.priority, r.match, r.pattern, names.get(r.category_id, "?"), r.sign or ""]
            for r in store.list_rules()]
    print(table(["id", "prio", "match", "pattern", "category", "sign"], rows, "rrllll"))


def cmd_rules_delete(args):
    store = _store(args)
    store.delete_rule(args.id)
    print(f"deleted rule {args.id}")


def cmd_rules_apply(args):
    store = _store(args)
    account_id = store.get_account(args.account).id if args.account else None
    changed = rules.apply_rules(store, account_id=account_id, only_uncategorized=not args.all)
    print(f"categorised {changed} transaction(s)")


# --- reports, budgets, export ---------------------------------------------------

def cmd_report_monthly(args):
    store = _store(args)
    year, month = parse_month(args.month)
    account_id = store.get_account(args.account).id if args.account else None
    rep = reports.monthly(store, year, month, account_id)
    if args.json:
        print(dumps(rep.to_json()))
        return
    print(f"{rep.month}: {rep.count} transactions")
    print(f"  income    {format_cents(rep.income_cents):>12}")
    print(f"  spending  {format_cents(rep.spending_cents):>12}")
    print(f"  net       {format_cents(rep.net_cents):>12}  ({rep.savings_rate}% saved)")
    for name, cents in sorted(rep.by_category.items(), key=lambda kv: kv[1]):
        print(f"    {name:<20}{format_cents(cents):>12}")


def cmd_report_year(args):
    store = _store(args)
    rows = []
    for rep in reports.yearly(store, int(args.year)):
        rows.append([rep.month, format_cents(rep.income_cents),
                     format_cents(rep.spending_cents), format_cents(rep.net_cents)])
    print(table(["month", "income", "spending", "net"], rows, "lrrr"))


def cmd_budget_set(args):
    store = _store(args)
    category = store.get_category(args.category)
    store.set_budget(category.id, abs(parse_amount(args.amount)))
    print(f"budget for {category.name}: {format_cents(abs(parse_amount(args.amount)))}")


def cmd_budget_status(args):
    store = _store(args)
    lines = budget_mod.status(store, *parse_month(args.month))
    rows = [[l.category, format_cents(l.budget_cents), format_cents(l.spent_cents),
             format_cents(l.remaining_cents), "OVER" if l.over else ""] for l in lines]
    print(table(["category", "budget", "spent", "left", ""], rows, "lrrrl"))


def cmd_export(args):
    store = _store(args)
    account = store.get_account(args.account)
    if args.out:
        with open(args.out, "w", newline="") as fh:
            export_csv(store, account, fh)
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(export_csv(store, account))


# --- parser -----------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="pennywise", description="Personal finance ledger.")
    p.add_argument("--db", help="database file (default: $PENNYWISE_DB or ~/.pennywise/pennywise.db)")
    sub = p.add_subparsers(dest="command", required=True)

    acc = sub.add_parser("accounts", help="manage accounts").add_subparsers(dest="action", required=True)
    a = acc.add_parser("add")
    a.add_argument("name")
    a.add_argument("--bank", choices=BANKS, default="manual")
    a.add_argument("--currency")
    a.add_argument("--opened")
    a.set_defaults(func=cmd_accounts_add)
    a = acc.add_parser("list")
    a.add_argument("--all", action="store_true", help="include closed accounts")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_accounts_list)
    a = acc.add_parser("show")
    a.add_argument("name")
    a.set_defaults(func=cmd_accounts_show)
    a = acc.add_parser("close")
    a.add_argument("name")
    a.set_defaults(func=cmd_accounts_close)

    txn = sub.add_parser("txn", help="transactions").add_subparsers(dest="action", required=True)
    t = txn.add_parser("add")
    t.add_argument("--account", required=True)
    t.add_argument("--date", required=True, help="YYYY-MM-DD")
    t.add_argument("--amount", required=True, help="positive = money in, negative = money out")
    t.add_argument("--desc", required=True)
    t.add_argument("--category")
    t.add_argument("--note")
    t.set_defaults(func=cmd_txn_add)
    t = txn.add_parser("list")
    t.add_argument("--account")
    t.add_argument("--month", help="YYYY-MM")
    t.add_argument("--category")
    t.add_argument("--uncategorized", action="store_true")
    t.add_argument("--limit", type=int)
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_txn_list)
    t = txn.add_parser("categorize")
    t.add_argument("id", type=int)
    t.add_argument("category")
    t.set_defaults(func=cmd_txn_categorize)
    t = txn.add_parser("delete")
    t.add_argument("id", type=int)
    t.set_defaults(func=cmd_txn_delete)

    cat = sub.add_parser("categories", help="categories").add_subparsers(dest="action", required=True)
    c = cat.add_parser("add")
    c.add_argument("name")
    c.add_argument("--kind", choices=CATEGORY_KINDS, default="expense")
    c.add_argument("--parent")
    c.set_defaults(func=cmd_categories_add)
    c = cat.add_parser("list")
    c.set_defaults(func=cmd_categories_list)

    rl = sub.add_parser("rules", help="categorisation rules").add_subparsers(dest="action", required=True)
    r = rl.add_parser("add")
    r.add_argument("pattern")
    r.add_argument("--category", required=True)
    r.add_argument("--match", choices=RULE_MATCHES, default="contains")
    r.add_argument("--priority", type=int, default=100)
    r.add_argument("--account")
    r.add_argument("--sign", choices=("in", "out"))
    r.set_defaults(func=cmd_rules_add)
    r = rl.add_parser("list")
    r.set_defaults(func=cmd_rules_list)
    r = rl.add_parser("delete")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rules_delete)
    r = rl.add_parser("apply", help="categorise existing transactions")
    r.add_argument("--account")
    r.add_argument("--all", action="store_true", help="also re-check categorised ones")
    r.set_defaults(func=cmd_rules_apply)

    rep = sub.add_parser("report", help="reports").add_subparsers(dest="action", required=True)
    r = rep.add_parser("monthly")
    r.add_argument("month", help="YYYY-MM")
    r.add_argument("--account")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_report_monthly)
    r = rep.add_parser("year")
    r.add_argument("year")
    r.set_defaults(func=cmd_report_year)

    bud = sub.add_parser("budget", help="monthly budgets").add_subparsers(dest="action", required=True)
    b = bud.add_parser("set")
    b.add_argument("category")
    b.add_argument("amount")
    b.set_defaults(func=cmd_budget_set)
    b = bud.add_parser("status")
    b.add_argument("month", help="YYYY-MM")
    b.set_defaults(func=cmd_budget_status)

    e = sub.add_parser("export", help="write an account's transactions as CSV")
    e.add_argument("--account", required=True)
    e.add_argument("--out")
    e.set_defaults(func=cmd_export)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except PennywiseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
