import pytest

from payouts.errors import MoneyError
from payouts.money import apply_bps, format_cents, parse_amount, sum_cents


@pytest.mark.parametrize(
    "text,cents",
    [("19.99", 1999), ("19.9", 1990), ("19", 1900), ("$5.00", 500), ("1,019.99", 101999), (" 0.01 ", 1), ("0.10", 10)],
)
def test_parse_amount(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "1.999", "-5", "0", "NaN", "Infinity", "1e400"])
def test_parse_amount_rejects(text):
    with pytest.raises(MoneyError):
        parse_amount(text)


def test_parse_amount_allow_zero():
    assert parse_amount("0.00", allow_zero=True) == 0


def test_parse_amount_rejects_float():
    with pytest.raises(MoneyError):
        parse_amount(19.99)


def test_parse_amount_int_is_dollars():
    assert parse_amount(20) == 2000


@pytest.mark.parametrize("cents,text", [(1999, "19.99"), (5, "0.05"), (0, "0.00"), (-50, "-0.50"), (123456, "1234.56")])
def test_format_cents(cents, text):
    assert format_cents(cents) == text


def test_format_cents_signed():
    assert format_cents(1999, signed=True) == "+19.99"
    assert format_cents(-1999, signed=True) == "-19.99"
    assert format_cents(0, signed=True) == "0.00"


def test_format_cents_rejects_float():
    with pytest.raises(TypeError):
        format_cents(19.99)


def test_apply_bps_rounds_half_up():
    assert apply_bps(1000, 290) == 29
    assert apply_bps(1999, 290) == 58  # 57.971
    assert apply_bps(50, 100) == 1  # 0.5 -> 1


def test_sum_cents():
    assert sum_cents([1, 2, 3]) == 6
    with pytest.raises(TypeError):
        sum_cents([1, 0.5])


def test_jpy_has_no_minor_unit():
    assert parse_amount("500", "JPY") == 500
    assert parse_amount("¥1,200", "JPY") == 1200
    assert format_cents(500, "JPY") == "500"
    assert format_cents(-1200, "JPY") == "-1200"
    with pytest.raises(MoneyError):
        parse_amount("500.5", "JPY")


def test_currency_matters():
    assert parse_amount("500") == 50000
    assert parse_amount("500", "jpy") == 500


def test_unknown_currency():
    with pytest.raises(MoneyError):
        parse_amount("1.00", "XYZ")
