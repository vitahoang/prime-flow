from datetime import date

import pytest

from tickoff.due import DueParseError, describe, parse_due

MON = date(2026, 10, 19)


@pytest.mark.parametrize("text,expected", [
    ("today", "2026-10-19"),
    ("tomorrow", "2026-10-20"),
    ("+3", "2026-10-22"),
    ("+2w", "2026-11-02"),
    ("fri", "2026-10-23"),
    ("monday", "2026-10-26"),
    ("next week", "2026-10-26"),
    ("2026-12-01", "2026-12-01"),
    ("11/3", "2026-11-03"),
    ("3 nov", "2026-11-03"),
    ("Nov 3", "2026-11-03"),
    ("1/5", "2027-01-05"),
])
def test_parse_due(text, expected):
    assert parse_due(text, MON) == expected


def test_none_values():
    for text in ("", "none", "never", "-"):
        assert parse_due(text, MON) is None


def test_errors():
    for text in ("someday", "2026-02-30", "13/45"):
        with pytest.raises(DueParseError):
            parse_due(text, MON)


def test_describe():
    assert describe(None, MON) == ""
    assert describe("2026-10-19", MON) == "today"
    assert describe("2026-10-20", MON) == "tomorrow"
    assert describe("2026-10-18", MON) == "yesterday"
    assert describe("2026-10-16", MON) == "3d late"
    assert describe("2026-10-23", MON) == "fri"
    assert describe("2026-12-01", MON) == "2026-12-01"
