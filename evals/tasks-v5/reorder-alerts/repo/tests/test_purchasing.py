from datetime import date

from stockroom.models import POStatus
from stockroom.purchasing import (counts_by_status, lines_by_supplier, list_orders, next_po_id,
                                  order_value, overdue)


def test_list_orders_filters(inv):
    assert [po.id for po in list_orders(inv.purchase_orders, status=POStatus.OPEN)] == ["PO-0001"]
    assert [po.id for po in list_orders(inv.purchase_orders, shop="mkt")] == ["PO-0002", "PO-0001"]
    assert [po.id for po in list_orders(inv.purchase_orders, supplier="laminata")] == ["PO-0002"]


def test_order_value(inv):
    po = inv.purchase_orders[0]
    assert order_value(po, inv.suppliers["green-valley"]) == 36.0
    assert order_value(po, None) == 0.0


def test_overdue(inv):
    assert [po.id for po in overdue(inv.purchase_orders, date(2026, 10, 15))] == ["PO-0001"]
    assert overdue(inv.purchase_orders, date(2026, 10, 14)) == []


def test_counts_and_lines(inv):
    assert counts_by_status(inv.purchase_orders) == {"open": 1, "received": 1, "cancelled": 1}
    assert lines_by_supplier(inv.purchase_orders)["laminata"] == [("PO-0002", "CRD-SHEET", 100)]


def test_next_po_id(inv):
    assert next_po_id(inv.purchase_orders) == "PO-0004"
    assert next_po_id([]) == "PO-0001"
