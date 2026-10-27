from datetime import date
from decimal import Decimal

from invoicer import billing
from invoicer.models import Fee
from invoicer.store import Store

from .conftest import utc

NOW = utc(2026, 9, 15, 12, 0)


def _get(store, invoice_id):
    inv = store.invoice(invoice_id)
    return inv, store.customer_for(inv)


def test_due_date_london(store):
    inv, cust = _get(store, "INV-1")
    assert billing.due_date(inv, cust) == date(2026, 10, 1)


def test_due_date_v0_record(store):
    inv, cust = _get(store, "INV-0900")
    assert billing.due_date(inv, cust) == date(2025, 12, 3)


def test_balance_after_part_payment(store):
    inv, _ = _get(store, "INV-3")
    assert billing.balance(inv, store.payments) == Decimal("600.00")


def test_void_has_no_balance(store):
    inv, _ = _get(store, "INV-5")
    assert billing.balance(inv, store.payments) == 0


def test_statuses(store):
    assert billing.status(*_get(store, "INV-1"), store.payments, NOW) == billing.OPEN
    assert billing.status(*_get(store, "INV-4"), store.payments, NOW) == billing.PAID
    assert billing.status(*_get(store, "INV-5"), store.payments, NOW) == billing.VOID
    assert billing.status(*_get(store, "INV-0900"), store.payments, NOW) == billing.OVERDUE


def test_not_overdue_until_due_day_ends_in_london(store):
    inv, cust = _get(store, "INV-1")
    # Due 1 Oct; London is on BST, so the day ends at 23:00 UTC.
    assert not billing.is_overdue(inv, cust, store.payments, utc(2026, 10, 1, 22, 59))
    assert billing.is_overdue(inv, cust, store.payments, utc(2026, 10, 1, 23, 0))


def test_not_overdue_until_due_day_ends_in_los_angeles(store):
    inv, cust = _get(store, "INV-3")
    # Due 2 Oct, Pacific Daylight Time: the day ends 07:00 UTC on 3 Oct.
    assert not billing.is_overdue(inv, cust, store.payments, utc(2026, 10, 3, 6, 0))
    assert billing.is_overdue(inv, cust, store.payments, utc(2026, 10, 3, 7, 30))


def test_paid_invoice_is_never_overdue(store):
    inv, cust = _get(store, "INV-4")
    assert not billing.is_overdue(inv, cust, store.payments, utc(2027, 1, 1))


def test_late_fee_is_two_percent(store):
    inv, cust = _get(store, "INV-1")
    assert billing.late_fee(inv, cust, store.payments, utc(2026, 10, 5)) == Decimal("24.00")


def test_late_fee_has_a_minimum(store):
    inv, cust = _get(store, "INV-0900")
    assert billing.late_fee(inv, cust, store.payments, NOW) == Decimal("10.00")


def test_no_late_fee_before_due(store):
    inv, cust = _get(store, "INV-1")
    assert billing.late_fee(inv, cust, store.payments, NOW) == 0


def test_amount_due_includes_fee(store):
    inv, cust = _get(store, "INV-1")
    assert billing.amount_due(inv, cust, store.payments, utc(2026, 10, 5)) == Decimal("1224.00")


def test_days_overdue(store):
    inv, cust = _get(store, "INV-1")
    assert billing.days_overdue(inv, cust, utc(2026, 10, 5, 12)) == 4


def test_overdue_invoices(store):
    found = billing.overdue_invoices(store, NOW)
    assert [inv.id for inv, _ in found] == ["INV-0900"]


def test_overdue_run_charges_each_invoice_once(store, data_dir):
    new = billing.charge_late_fees(store, utc(2026, 10, 5))
    assert sorted(f.invoice_id for f in new) == ["INV-0900", "INV-1", "INV-2", "INV-3"]
    assert billing.charge_late_fees(Store(data_dir), utc(2026, 10, 6)) == []
    assert len(Store(data_dir).fees) == 4


def test_charged_fee_is_what_is_owed(store):
    store.add_fee(Fee("INV-1", Decimal("30.00"), utc(2026, 10, 2)))
    inv, cust = _get(store, "INV-1")
    assert billing.late_fee(inv, cust, store.payments, utc(2026, 10, 5), store.fees) == Decimal("30.00")
    assert billing.amount_due(inv, cust, store.payments, utc(2026, 10, 5), store.fees) == Decimal("1230.00")
