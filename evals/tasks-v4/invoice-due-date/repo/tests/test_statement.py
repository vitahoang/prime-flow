from decimal import Decimal

from invoicer import statement

from .conftest import utc


def test_rows_skip_void(store):
    rows = statement.statement_rows(store, store.customer("C1"), utc(2026, 9, 15, 12))
    assert [r["invoice"].id for r in rows] == ["INV-0900", "INV-1", "INV-4"]


def test_aging_buckets(store):
    rows = statement.statement_rows(store, store.customer("C1"), utc(2026, 10, 20, 12))
    ages = statement.aging(rows)
    assert ages["1-30"] == Decimal("1224.00")  # INV-1, 19 days late, with fee
    assert ages["60+"] == Decimal("210.00")  # INV-0900 plus minimum fee


def test_render_statement(store):
    out = statement.render_statement(store, store.customer("C1"), utc(2026, 9, 15, 12))
    assert "statement for Northgate Books" in out
    assert "As of 15 Sep 2026" in out
    assert "Total outstanding: GBP 1,410.00" in out
