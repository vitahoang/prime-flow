from datetime import date

from stockroom.formatting import fmt_date, fmt_money, fmt_qty, heading, table
from stockroom.units import convert, plural

import pytest


def test_fmt_qty():
    assert fmt_qty(12) == "12"
    assert fmt_qty(2.5, "kg") == "2.5 kg"
    assert fmt_qty(1, "carton") == "1 carton"
    assert fmt_qty(3, "loaf") == "3 loaves"


def test_fmt_money_and_date():
    assert fmt_money(1234.5) == "£1,234.50"
    assert fmt_date(date(2026, 10, 15)) == "Thu 15 Oct"
    assert fmt_date(None) == "-"


def test_table_alignment():
    out = table(["Name", "Qty"], [["oat", 12], ["croissant", 3]])
    lines = out.splitlines()
    assert lines[0].startswith("Name")
    assert set(lines[1].replace(" ", "")) == {"-"}
    assert lines[2].endswith("12")
    assert lines[3].startswith("croissant")


def test_heading():
    assert heading("Stock") == "Stock\n====="


def test_units():
    assert plural("box", 2) == "boxes"
    assert convert(500, "g", "kg") == 0.5
    with pytest.raises(ValueError):
        convert(1, "kg", "l")
