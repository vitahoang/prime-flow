from decimal import Decimal

from meterly import tax


def test_rate_for_known_countries():
    assert tax.rate_for("GB") == Decimal("0.20")
    assert tax.rate_for("de") == Decimal("0.19")
    assert tax.rate_for("JP") == Decimal("0.10")


def test_rate_for_unregistered_country_is_zero():
    assert tax.rate_for("US") == 0
    assert tax.rate_for("") == 0


def test_describe():
    assert tax.describe("GB") == "VAT 20%"
    assert tax.describe("AU") == "GST 10%"
    assert tax.describe("US") == "no tax"
