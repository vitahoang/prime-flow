from datetime import date

import pytest

from pennywise.dates import iter_months, month_bounds, parse_date, parse_iso, parse_month
from pennywise.errors import InvalidInput


def test_parse_date_default_is_day_first():
    assert parse_date("03/04/2025") == date(2025, 4, 3)


def test_parse_date_with_format():
    assert parse_date("14.08.2025", "%d.%m.%Y") == date(2025, 8, 14)


def test_parse_date_rejects_garbage():
    with pytest.raises(InvalidInput):
        parse_date("2025-13-45")
    with pytest.raises(InvalidInput):
        parse_date("")


def test_parse_iso_and_month():
    assert parse_iso("2025-02-28") == date(2025, 2, 28)
    assert parse_month("2025-02") == (2025, 2)
    with pytest.raises(InvalidInput):
        parse_month("2025-13")


def test_month_bounds_leap_year():
    assert month_bounds(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))


def test_iter_months_crosses_year():
    months = list(iter_months(date(2024, 11, 5), date(2025, 2, 1)))
    assert months == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]
