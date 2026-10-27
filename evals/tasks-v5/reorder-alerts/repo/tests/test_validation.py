from stockroom.store import load
from stockroom.validation import check

from conftest import ITEMS, MOVEMENTS, write_data


def test_sample_data_is_clean(inv):
    assert check(inv) == []


def test_unmatched_transfer(tmp_path):
    moves = MOVEMENTS + [("2026-10-14", "HAR", "OAT-1L", "transfer_out", 2, "T9", "")]
    problems = check(load(write_data(tmp_path / "d", movements=moves)))
    assert any("T9" in p and "never received" in p for p in problems)


def test_unknown_supplier_and_negative_stock(tmp_path):
    items = ITEMS + [{"sku": "MYSTERY", "name": "?", "unit": "each", "supplier": "nobody"}]
    moves = MOVEMENTS + [("2026-10-14", "STN", "MYSTERY", "sale", 1, "", "")]
    problems = check(load(write_data(tmp_path / "d", items=items, movements=moves)))
    assert any("nobody" in p for p in problems)
    assert any("STN MYSTERY: stock below zero" in p for p in problems)
