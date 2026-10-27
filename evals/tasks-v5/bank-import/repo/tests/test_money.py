import pytest

from pennywise.errors import InvalidInput
from pennywise.money import format_cents, parse_amount, percent, split_evenly, to_decimal_str


@pytest.mark.parametrize("text,cents", [
    ("4.50", 450),
    ("-4.50", -450),
    ("1,234.56", 123456),
    ("(12.00)", -1200),
    ("12.00-", -1200),
    ("£7", 700),
    ("+3.1", 310),
    (".99", 99),
])
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


def test_parse_amount_decimal_comma():
    assert parse_amount("1.234,56", decimal=",") == 123456
    assert parse_amount("-8,90", decimal=",") == -890


@pytest.mark.parametrize("bad", ["", "  ", "abc", "1.234", "4.5.6"])
def test_parse_amount_rejects(bad):
    with pytest.raises(InvalidInput):
        parse_amount(bad)


def test_format_and_decimal_str():
    assert format_cents(-123456, "GBP") == "-£1,234.56"
    assert format_cents(5) == "0.05"
    assert to_decimal_str(-450) == "-4.50"
    assert to_decimal_str(100000) == "1000.00"


def test_split_evenly_adds_up():
    assert split_evenly(1000, 3) == [334, 333, 333]
    assert sum(split_evenly(-1001, 4)) == -1001


def test_percent():
    assert percent(1, 4) == 25.0
    assert percent(1, 0) == 0.0
