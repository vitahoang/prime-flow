import random
from datetime import date, datetime, timedelta, timezone

import pytest

from invoicer import dates

from .conftest import utc


@pytest.mark.parametrize(
    "raw, days",
    [("Net 30", 30), ("net-15", 15), ("NET 45", 45), ("30", 30), (14, 14), ("30 days", 30), ("Due on receipt", 0)],
)
def test_parse_terms(raw, days):
    assert dates.parse_terms(raw) == days


@pytest.mark.parametrize("raw", ["", None, "monthly", "Net thirty"])
def test_parse_terms_rejects_garbage(raw):
    with pytest.raises(ValueError):
        dates.parse_terms(raw)


def test_format_terms():
    assert dates.format_terms(30) == "Net 30"
    assert dates.format_terms(0) == "Due on receipt"


def test_due_date_from_timestamp():
    assert dates.local_due_date(utc(2026, 9, 1, 10, 0), 30, "Europe/London") == date(2026, 10, 1)


def test_due_date_net_15():
    assert dates.local_due_date(utc(2026, 9, 3, 2, 0), 15, "Asia/Singapore") == date(2026, 9, 18)


def test_due_date_crosses_month_and_year():
    assert dates.local_due_date(utc(2026, 12, 10, 12, 0), 30, "Europe/London") == date(2027, 1, 9)


def test_due_date_for_v0_record_is_issue_date_plus_terms():
    assert dates.local_due_date(date(2025, 11, 3), 30, "Europe/London") == date(2025, 12, 3)


def test_end_of_local_day_london_summer():
    assert dates.end_of_local_day(date(2026, 7, 1), "Europe/London") == utc(2026, 7, 1, 23, 0)


def test_end_of_local_day_singapore():
    assert dates.end_of_local_day(date(2026, 3, 10), "Asia/Singapore") == utc(2026, 3, 10, 16, 0)


SAMPLE_ZONES = [
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "Asia/Dubai",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Australia/Sydney",
    "America/New_York",
    "America/Chicago",
    "Pacific/Honolulu",
]


def test_end_of_local_day_is_close_to_utc_midnight():
    # Spot-check one of our customers' zones: the end of a local day is never
    # far from UTC midnight.
    tz = random.choice(SAMPLE_ZONES)
    end = dates.end_of_local_day(date(2026, 3, 10), tz)
    assert abs(end - datetime(2026, 3, 11, tzinfo=timezone.utc)) < timedelta(hours=9)


def test_days_late_and_until():
    assert dates.days_late(date(2026, 10, 1), date(2026, 10, 4)) == 3
    assert dates.days_late(date(2026, 10, 1), date(2026, 9, 30)) == 0
    assert dates.days_until(date(2026, 10, 1), date(2026, 9, 24)) == 7


def test_reminder_date():
    assert dates.reminder_date(date(2026, 10, 1), 7) == date(2026, 9, 24)


@pytest.mark.parametrize("days, bucket", [(0, "current"), (-3, "current"), (1, "1-30"), (30, "1-30"), (31, "31-60"), (61, "60+")])
def test_aging_bucket(days, bucket):
    assert dates.aging_bucket(days) == bucket


def test_add_business_days_skips_weekend():
    assert dates.add_business_days(date(2026, 10, 9), 1) == date(2026, 10, 12)  # Fri -> Mon


def test_month_bounds():
    assert dates.month_bounds(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert dates.month_bounds(2026, 12) == (date(2026, 12, 1), date(2026, 12, 31))
