from decimal import Decimal

import pytest

from meterly import money


def test_parse_amount_accepts_strings_and_ints():
    assert money.parse_amount("49.00") == Decimal("49.00")
    assert money.parse_amount(3) == Decimal(3)
    assert money.parse_amount("") == Decimal(0)


def test_parse_amount_rejects_floats():
    with pytest.raises(money.MoneyError):
        money.parse_amount(0.1)


def test_round_half_up():
    assert money.round_half_up(Decimal("2.345")) == Decimal("2.35")
    assert money.round_half_up(Decimal("2.344")) == Decimal("2.34")
    assert money.round_half_up(Decimal("2.5"), 0) == Decimal("3")


def test_to_cents():
    assert money.to_cents(Decimal("49.995")) == 5000
    assert money.to_cents(Decimal("0.01")) == 1


def test_exponent():
    assert money.exponent("usd") == 2
    assert money.exponent("JPY") == 0
    with pytest.raises(money.MoneyError):
        money.exponent("XYZ")


def test_format_amount():
    assert money.format_amount(4950, "USD") == "$49.50"
    assert money.format_amount(123456, "GBP") == "£1,234.56"
    assert money.format_amount(3000, "JPY") == "¥3,000"
    assert money.format_amount(-250, "EUR") == "-€2.50"


def test_format_major():
    assert money.format_major(Decimal("15000"), "JPY") == "¥15,000"
    assert money.format_major(Decimal("0.125"), "USD") == "$0.13"
