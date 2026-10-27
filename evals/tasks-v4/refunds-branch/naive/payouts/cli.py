"""Command line interface: ``python -m payouts COMMAND ...``.

Amounts on the command line are in major units of the merchant's currency
("19.99" dollars, "500" yen); they are converted to minor units with
money.parse_amount(text, merchant.currency) as soon as they are read.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from payouts import charges, config, merchants, payout, refunds, statements
from payouts.errors import PayoutsError
from payouts.gateway import FakeGateway
from payouts.money import format_cents, parse_amount
from payouts.store import Store


def _store() -> Store:
    return Store()


def cmd_merchant_add(args: argparse.Namespace) -> int:
    store = _store()
    merchant = merchants.create_merchant(
        store,
        args.name,
        fee_bps=args.fee_bps,
        fee_fixed_cents=args.fee_fixed_cents,
        email=args.email,
        currency=args.currency,
    )
    print(merchant.id)
    return 0


def cmd_merchant_list(args: argparse.Namespace) -> int:
    store = _store()
    for m in merchants.list_merchants(store, include_suspended=not args.active):
        print(f"{m.id}\t{m.name}\t{m.currency}\t{m.status}\t{m.fee_bps}bps+{m.fee_fixed_cents}")
    return 0


def cmd_merchant_suspend(args: argparse.Namespace) -> int:
    store = _store()
    m = merchants.suspend_merchant(store, args.merchant_id)
    print(f"{m.id} suspended")
    return 0


def cmd_charge(args: argparse.Namespace) -> int:
    store = _store()
    merchant = merchants.get_merchant(store, args.merchant_id)
    amount = parse_amount(args.amount, merchant.currency)
    charge = charges.create_charge(store, FakeGateway(store), merchant.id, amount, args.description)
    cur = charge.currency
    print(f"{charge.id} charged {format_cents(charge.amount_cents, cur)} {cur} (fee {format_cents(charge.fee_cents, cur)})")
    return 0


def cmd_refund(args: argparse.Namespace) -> int:
    store = _store()
    r = refunds.create_refund(store, FakeGateway(store), args.charge_id, args.amount, reason=args.reason)
    print(f"{r.id} refunded {format_cents(r.amount_cents, r.currency)} {r.currency} of {r.charge_id}")
    return 0


def cmd_void(args: argparse.Namespace) -> int:
    store = _store()
    charge = charges.void_charge(store, FakeGateway(store), args.charge_id)
    print(f"{charge.id} voided")
    return 0


def cmd_statement(args: argparse.Namespace) -> int:
    store = _store()
    print(statements.render(statements.build_statement(store, args.merchant_id)))
    return 0


def cmd_payout(args: argparse.Namespace) -> int:
    store = _store()
    merchant = merchants.get_merchant(store, args.merchant_id)
    amount = parse_amount(args.amount, merchant.currency) if args.amount is not None else None
    p = payout.create_payout(store, FakeGateway(store), merchant.id, amount)
    print(f"{p.id} paid out {format_cents(p.amount_cents, merchant.currency)} {merchant.currency}")
    return 0


def cmd_gateway_log(args: argparse.Namespace) -> int:
    """Dev helper: what the fake processor has committed, one line each."""
    store = _store()
    for op in FakeGateway(store, faults=[]).operations():
        target = op.get("charge_ref") or op.get("merchant_id") or "-"
        print(f"{op['op']}\t{op['ref']}\t{target}\t{op['amount_cents']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m payouts", description="Marketplace payouts.")
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("merchant", help="manage merchants")
    msub = m.add_subparsers(dest="merchant_command", required=True)
    add = msub.add_parser("add", help="create a merchant")
    add.add_argument("name")
    add.add_argument("--fee-bps", type=int, default=None, help="percentage fee in basis points")
    add.add_argument("--fee-fixed-cents", type=int, default=None, help="fixed fee per charge, in minor units")
    add.add_argument("--email")
    add.add_argument("--currency", default="USD", help="settlement currency: USD, EUR, GBP or JPY")
    add.set_defaults(func=cmd_merchant_add)
    ls = msub.add_parser("list", help="list merchants")
    ls.add_argument("--active", action="store_true", help="hide suspended merchants")
    ls.set_defaults(func=cmd_merchant_list)
    sus = msub.add_parser("suspend", help="stop a merchant taking charges")
    sus.add_argument("merchant_id")
    sus.set_defaults(func=cmd_merchant_suspend)

    c = sub.add_parser("charge", help="charge a customer for a merchant")
    c.add_argument("merchant_id")
    c.add_argument("amount", help="in the merchant's currency, e.g. 19.99 or 500 (JPY)")
    c.add_argument("--description", default="")
    c.set_defaults(func=cmd_charge)

    r = sub.add_parser("refund", help="refund some or all of a charge")
    r.add_argument("charge_id")
    r.add_argument("amount", help="in the charge's currency, e.g. 19.99 or 500 (JPY)")
    r.add_argument("--reason")
    r.set_defaults(func=cmd_refund)

    v = sub.add_parser("void", help="cancel a charge that hasn't settled yet")
    v.add_argument("charge_id")
    v.set_defaults(func=cmd_void)

    s = sub.add_parser("statement", help="print a merchant statement")
    s.add_argument("merchant_id")
    s.set_defaults(func=cmd_statement)

    p = sub.add_parser("payout", help="pay out a merchant's balance")
    p.add_argument("merchant_id")
    p.add_argument("amount", nargs="?", help="default is the whole balance")
    p.set_defaults(func=cmd_payout)

    g = sub.add_parser("gateway-log", help="(dev) show what the fake gateway has recorded")
    g.set_defaults(func=cmd_gateway_log)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # argparse defaults are None so `merchant add --help` doesn't print stale numbers
    if getattr(args, "fee_bps", 0) is None:
        args.fee_bps = config.DEFAULT_FEE_BPS
    if getattr(args, "fee_fixed_cents", 0) is None:
        args.fee_fixed_cents = config.DEFAULT_FEE_FIXED_CENTS
    try:
        return args.func(args)
    except PayoutsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
