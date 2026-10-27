from datetime import datetime

import pytest

from jotter import dates


def test_parse_forms():
    assert dates.parse("2024-03-02") == datetime(2024, 3, 2)
    assert dates.parse("2024-03-02T09:15:00") == datetime(2024, 3, 2, 9, 15)
    assert dates.parse("") is None
    with pytest.raises(dates.BadDate):
        dates.parse("March 2nd")


def test_humanize():
    now = datetime(2026, 5, 1, 12)
    assert dates.humanize(datetime(2026, 5, 1, 8), now) == "today"
    assert dates.humanize(datetime(2026, 4, 30), now) == "yesterday"
    assert dates.humanize(datetime(2026, 4, 20), now) == "11 days ago"
    assert dates.humanize(datetime(2026, 3, 20), now) == "6 weeks ago"
    assert dates.humanize(datetime(2020, 1, 1), now) == "6 years ago"
