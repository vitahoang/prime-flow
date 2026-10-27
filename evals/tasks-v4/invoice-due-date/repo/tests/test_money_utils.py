from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from invoicer import money, utils


def test_format_money():
    assert money.format_money(Decimal("1200"), "SGD") == "SGD 1,200.00"
    assert money.format_money(Decimal("-5.5"), "GBP") == "GBP -5.50"
    assert money.format_money(Decimal("1500"), "JPY") == "JPY 1,500"


def test_round_half_up():
    assert money.round_money(Decimal("2.005")) == Decimal("2.01")


def test_parse_amount():
    assert money.parse_amount("1,200.50") == Decimal("1200.50")
    assert money.parse_amount(3) == Decimal("3")
    with pytest.raises(ValueError):
        money.parse_amount("abc")


def test_format_date_styles():
    d = date(2026, 10, 4)
    assert utils.format_date(d) == "4 Oct 2026"
    assert utils.format_date(d, "short") == "04/10/26"
    assert utils.format_date(d, "iso") == "2026-10-04"


def test_format_date_accepts_datetime():
    assert utils.format_date(datetime(2026, 10, 4, 9, tzinfo=timezone.utc)) == "4 Oct 2026"


def test_format_date_rejects_strings():
    with pytest.raises(TypeError):
        utils.format_date("2026-10-04")


def test_plural_and_pad():
    assert utils.plural(1, "day") == "1 day"
    assert utils.plural(3, "day") == "3 days"
    assert utils.pad("abcdef", 4) == "abc…"
    assert utils.pad("ab", 4, "right") == "  ab"


def test_slugify():
    assert utils.slugify("Lim & Tan Pte Ltd") == "lim-tan-pte-ltd"
