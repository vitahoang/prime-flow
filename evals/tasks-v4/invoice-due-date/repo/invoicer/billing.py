"""Balances, overdue status and late fees."""

from datetime import datetime
from decimal import Decimal

from . import config, dates, money
from .models import Customer, Fee, Invoice, Payment

OPEN = "OPEN"
PAID = "PAID"
OVERDUE = "OVERDUE"
VOID = "VOID"


def due_date(invoice: Invoice, customer: Customer):
    """When the invoice falls due (see dates.local_due_date)."""
    return dates.local_due_date(invoice.issued, invoice.terms_days)


def amount_paid(invoice: Invoice, payments: list[Payment]) -> Decimal:
    return money.sum_money(
        (p.amount for p in payments if p.invoice_id == invoice.id), invoice.currency
    )


def balance(invoice: Invoice, payments: list[Payment]) -> Decimal:
    if invoice.void:
        return Decimal("0")
    return invoice.total - amount_paid(invoice, payments)


def is_overdue(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime) -> bool:
    """Overdue once the due day has fully ended for the customer and money is
    still owed. Nobody is late while it is still the due date where they are."""
    if invoice.void or balance(invoice, payments) <= 0:
        return False
    deadline = dates.end_of_local_day(due_date(invoice, customer), customer.timezone)
    return now >= deadline


def fee_to_charge(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime) -> Decimal:
    """The late fee an overdue invoice attracts right now, or 0."""
    if not is_overdue(invoice, customer, payments, now):
        return Decimal("0")
    owed = balance(invoice, payments)
    fee = money.percent(owed, config.LATE_FEE_RATE, invoice.currency)
    return max(fee, money.round_money(config.LATE_FEE_MINIMUM, invoice.currency))


def charged_fees(invoice: Invoice, fees: list[Fee]) -> list[Fee]:
    return [f for f in fees if f.invoice_id == invoice.id]


def late_fee(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime, fees=()) -> Decimal:
    """The late fee on an invoice: what has been charged (fees.json) or, if it
    is overdue and nothing is charged yet, what the next `overdue` run charges."""
    charged = charged_fees(invoice, fees)
    if charged:
        return money.sum_money((f.amount for f in charged), invoice.currency)
    return fee_to_charge(invoice, customer, payments, now)


def amount_due(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime, fees=()) -> Decimal:
    return balance(invoice, payments) + late_fee(invoice, customer, payments, now, fees)


def status(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime) -> str:
    if invoice.void:
        return VOID
    if balance(invoice, payments) <= 0:
        return PAID
    if is_overdue(invoice, customer, payments, now):
        return OVERDUE
    return OPEN


def days_overdue(invoice: Invoice, customer: Customer, now: datetime) -> int:
    from . import clock

    today = clock.local_today(customer.timezone, now)
    return dates.days_late(due_date(invoice, customer), today)


def charge_late_fees(store, now: datetime) -> list[Fee]:
    """Charge the late fee on every overdue invoice that has none yet.
    Run once a day by `overdue`; each invoice is charged at most once."""
    new = []
    for inv, cust in overdue_invoices(store, now):
        if charged_fees(inv, store.fees):
            continue
        fee = Fee(inv.id, fee_to_charge(inv, cust, store.payments, now), now)
        store.add_fee(fee)
        new.append(fee)
    return new


def overdue_invoices(store, now: datetime) -> list[tuple[Invoice, Customer]]:
    out = []
    for inv in store.all_invoices():
        cust = store.customer_for(inv)
        if is_overdue(inv, cust, store.payments, now):
            out.append((inv, cust))
    return out
