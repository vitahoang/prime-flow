from datetime import date

import pytest

from stockroom.ledger import (chain_totals, filter_movements, last_movement, negative_stock,
                              on_hand, on_hand_by_shop, outflow_by_sku, window)
from stockroom.models import MovementType


def test_on_hand_by_shop(inv):
    levels = on_hand_by_shop(inv.movements)
    assert levels[("HAR", "OAT-1L")] == 48 - 10 - 2 - 6
    assert levels[("STN", "OAT-1L")] == 6
    assert levels[("MKT", "OAT-1L")] == 36 - 12 - 5
    assert levels[("MKT", "CRD-SHEET")] == 70


def test_on_hand_chain_and_shop(inv):
    assert on_hand(inv.movements, "OAT-1L") == 30 + 6 + 19
    assert on_hand(inv.movements, "oat-1l", shop="mkt") == 19


def test_on_hand_as_of(inv):
    assert on_hand(inv.movements, "OAT-1L", shop="HAR", as_of=date(2026, 10, 2)) == 38


def test_chain_totals(inv):
    totals = chain_totals(on_hand_by_shop(inv.movements))
    assert totals == {"OAT-1L": 55, "CRD-SHEET": 70}


def test_filter_movements(inv):
    sales = filter_movements(inv.movements, types=[MovementType.SALE])
    assert len(sales) == 3
    recent = filter_movements(inv.movements, shop="MKT", since=date(2026, 10, 12))
    assert [m.type for m in recent] == [MovementType.RETURN, MovementType.SALE, MovementType.SALE]


def test_outflow_by_sku(inv):
    out = outflow_by_sku(inv.movements, since=date(2026, 10, 1), shop="HAR")
    assert out == {"OAT-1L": 18}


def test_last_movement(inv):
    m = last_movement(inv.movements, "OAT-1L", "MKT", MovementType.DELIVERY)
    assert m.ref == "D2"
    assert last_movement(inv.movements, "OAT-1L", "STN", MovementType.SALE) is None


def test_window():
    assert window(date(2026, 10, 15), 7) == (date(2026, 10, 9), date(2026, 10, 15))
    with pytest.raises(ValueError):
        window(date(2026, 10, 15), 0)


def test_negative_stock():
    assert negative_stock({("HAR", "A"): -1, ("HAR", "B"): 0, ("MKT", "A"): 3}) == [("HAR", "A")]
