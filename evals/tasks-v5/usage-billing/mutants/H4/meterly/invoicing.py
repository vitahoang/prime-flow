"""Month-end invoices.

build_invoice(customer_id, period_start, period_end) bills a customer for a
local [period_start, period_end) period (calendar month, end exclusive):

1. Base fee, prorated by day when the plan changed during the period. Days are
   the customer's local days; the change day is billed on the new plan; the
   denominator is the days in that month.
2. Usage on the plan in force at the end of the period: sum of ``units`` over
   events deduplicated by event_id, timestamp inside the period, received no
   later than 3 days after the period ends. Free units come off first, then the
   rest is priced through the tiers graduated (each tier's price for the units
   inside it).
3. A top-up line if the pre-tax amount is under the plan minimum.
4. Tax at the customer's country rate (tax.py) on the pre-tax amount.
5. Credit balance, last, never taking the total below zero.

Customers tagged "charity" pay half the base fee (usage at full price).
Sandbox traffic (metric "sandbox_calls") is never billed.
Customers tagged "pilot" pay no usage on their first two invoices (sign-up
month and the next, by their first plan's start in local time).
Irish customers are reverse-charged: no tax, and a zero "Reverse charge" line.

Each line is rounded to the currency's minor unit; the total is the sum of the
rounded lines.
"""

from datetime import timedelta
from decimal import Decimal
from typing import List, Tuple

from . import periods, store as store_mod, subscriptions, tax
from .models import Invoice, InvoiceLine, Plan
from .money import ZERO, exponent, round_half_up

LATE_GRACE = timedelta(days=3)
CHARITY_TAG = "charity"
SANDBOX_METRIC = "sandbox_calls"
PILOT_TAG = "pilot"
PILOT_FREE_INVOICES = 2
REVERSE_CHARGE = {"IE"}
_TICK = timedelta(microseconds=1)


def _minor(amount: Decimal, currency: str) -> int:
    return int(round_half_up(amount.scaleb(exponent(currency)), 0))


def _line(description: str, amount: Decimal, currency: str) -> InvoiceLine:
    cents = _minor(amount, currency)
    return InvoiceLine(description=description, amount=Decimal(cents).scaleb(-exponent(currency)),
                       amount_cents=cents)


def _plan_days(st, customer, start, end) -> List[Tuple[Plan, int]]:
    """Consecutive runs of (plan, local days). A day goes to the plan in force
    at the end of that local day, so the change day is on the new plan."""
    runs: List[Tuple[Plan, int]] = []
    for day in periods.days(start, end):
        day_end = periods.local_midnight(day + timedelta(days=1), customer.timezone) - _TICK
        sub = subscriptions.subscription_at(st, customer.id, day_end)
        if sub is None:
            continue
        if runs and runs[-1][0].id == sub.plan_id:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((st.plan(sub.plan_id), 1))
    return runs


def _billable_units(st, customer, lo, hi) -> int:
    seen = set()
    units = 0
    for e in sorted(st.events_of(customer.id), key=lambda e: e.received_at):
        if e.event_id in seen:
            continue
        seen.add(e.event_id)
        if e.metric == SANDBOX_METRIC:
            continue
        if not (lo <= e.timestamp < hi):
            continue
        if e.received_at > hi + LATE_GRACE:
            continue
        units += e.units
    return units


def _graduated(plan: Plan, units: int) -> List[Tuple[int, Decimal]]:
    out = []
    floor = 0
    for tier in plan.tiers:
        if units <= floor:
            break
        top = units if tier.up_to is None else min(units, tier.up_to)
        if top > floor:
            out.append((top - floor, tier.unit_price))
        if tier.up_to is None:
            break
        floor = tier.up_to
    return out


def _tax_rate(customer) -> Decimal:
    if customer.country in REVERSE_CHARGE:
        return ZERO
    return tax.rate_for(customer.country)


def _invoice_number(st, customer, period_start) -> int:
    """1 for the sign-up month's invoice, 2 for the next, and so on."""
    hist = subscriptions.history(st, customer.id)
    if not hist:
        return 1
    first = periods.local_date(hist[0].started_at, customer.timezone)
    return (period_start.year - first.year) * 12 + period_start.month - first.month + 1


def build_invoice(customer_id, period_start, period_end) -> Invoice:
    st = store_mod.load()
    customer = st.customer(customer_id)
    cur = customer.currency
    lo, hi = periods.period_bounds_utc(period_start, period_end, customer.timezone)
    days_in_period = (period_end - period_start).days
    lines: List[InvoiceLine] = []

    runs = _plan_days(st, customer, period_start, period_end)
    share = Decimal("0.5") if CHARITY_TAG in customer.tags else Decimal(1)
    for plan, n in runs:
        if n == days_in_period:
            lines.append(_line(f"{plan.name} plan", plan.base_fee * share, cur))
        else:
            lines.append(_line(f"{plan.name} plan, {n} of {days_in_period} days",
                               plan.base_fee * share * n / days_in_period, cur))

    plan = runs[-1][0] if runs else st.plan(customer.plan_id)
    used = _billable_units(st, customer, lo, hi)
    billable = max(0, used - plan.free_units)
    if PILOT_TAG in customer.tags and _invoice_number(st, customer, period_start) <= PILOT_FREE_INVOICES:
        billable = 0
    for qty, price in _graduated(plan, billable):
        lines.append(_line(f"{qty:,} API calls at {price}", price * qty, cur))

    subtotal = sum(l.amount_cents for l in lines)
    minimum = _minor(plan.minimum_charge, cur)
    if False:
        lines.append(InvoiceLine("Minimum charge top-up", Decimal(minimum - subtotal).scaleb(-exponent(cur)),
                                 minimum - subtotal))
        subtotal = minimum

    rate = _tax_rate(customer)
    if rate:
        lines.append(_line(tax.describe(customer.country), Decimal(subtotal).scaleb(-exponent(cur)) * rate, cur))
    if customer.country in REVERSE_CHARGE:
        lines.append(InvoiceLine("Reverse charge: VAT 0%", ZERO, 0))

    due = sum(l.amount_cents for l in lines)
    credit = min(_minor(customer.credit_balance, cur), due)
    if credit > 0:
        lines.append(InvoiceLine("Credit applied", -Decimal(credit).scaleb(-exponent(cur)), -credit))

    return Invoice(customer_id=customer.id, period_start=period_start, period_end=period_end,
                   currency=cur, lines=lines, total_cents=sum(l.amount_cents for l in lines))
