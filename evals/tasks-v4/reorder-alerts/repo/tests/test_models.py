from datetime import date

import pytest

from stockroom.models import (INBOUND, OUTBOUND, Item, Movement, MovementType, POLine, POStatus,
                              PurchaseOrder, Supplier, SupplierItem)


def test_movement_type_direction():
    assert MovementType.DELIVERY.sign == 1
    assert MovementType.TRANSFER_IN.sign == 1
    for t in (MovementType.SALE, MovementType.WASTE, MovementType.TRANSFER_OUT, MovementType.RETURN):
        assert t.sign == -1
    assert INBOUND | OUTBOUND == set(MovementType)
    assert not INBOUND & OUTBOUND


def test_signed_qty():
    m = Movement(date(2026, 1, 1), "HAR", "OAT-1L", MovementType.SALE, 3)
    assert m.signed_qty == -3


def test_item_sku_normalised_and_min_stock_checked():
    assert Item(" oat-1l ", "Oat", "carton", "gv").sku == "OAT-1L"
    with pytest.raises(ValueError):
        Item("X", "X", "each", "gv", min_stock=-1)


def test_supplier_case_size_defaults_to_one():
    s = Supplier("gv", "Green Valley", 2, items={"OAT-1L": SupplierItem("OAT-1L", 12, 1.5)})
    assert s.case_size("oat-1l") == 12
    assert s.case_size("MILK-2L") == 1
    assert s.sells("OAT-1L") and not s.sells("MILK-2L")


def test_case_size_must_be_positive():
    with pytest.raises(ValueError):
        SupplierItem("X", 0)


def test_po_qty_for_sums_lines():
    po = PurchaseOrder("PO-1", "gv", "MKT", POStatus.OPEN, date(2026, 1, 1),
                       lines=[POLine("OAT-1L", 12), POLine("OAT-1L", 6), POLine("MILK-2L", 6)])
    assert po.qty_for("oat-1l") == 18
    assert po.skus == ["MILK-2L", "OAT-1L"]
    assert po.is_open()
