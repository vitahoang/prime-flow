from decimal import Decimal

from meterly import quote


def test_estimate_includes_base_fee(store):
    row = quote.estimate(store, "starter_gbp", 10000)
    assert row["base_fee"] == Decimal("29.00")
    assert row["total"] == row["base_fee"] + row["usage"]


def test_estimate_minimum(store):
    row = quote.estimate(store, "scale_usd", 10)
    assert row["total"] == Decimal("250.00")


def test_compare_skips_retired_and_filters_currency(store):
    rows = quote.compare(store, 20000, "GBP")
    assert [r["plan"] for r in rows] == ["starter_gbp", "pro_gbp"]
    assert all(r["plan"] != "legacy_usd" for r in quote.compare(store, 20000))


def test_render(store):
    text = quote.render(quote.estimate(store, "pro_jpy", 1000))
    assert "¥15,000" in text
