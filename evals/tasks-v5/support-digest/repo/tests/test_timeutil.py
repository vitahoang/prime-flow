from datetime import date, datetime, timedelta, timezone

import pytest

from helpdesk import timeutil


def test_iso_round_trip():
    dt = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)
    assert timeutil.parse_iso(timeutil.format_iso(dt)) == dt


def test_to_local_and_local_date():
    dt = datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc)
    assert timeutil.to_local(dt, "Asia/Ho_Chi_Minh").hour == 3
    assert timeutil.local_date(dt, "Asia/Ho_Chi_Minh") == date(2026, 10, 15)
    assert timeutil.local_date(dt, "America/Los_Angeles") == date(2026, 10, 14)


def test_unknown_zone():
    with pytest.raises(ValueError):
        timeutil.zone("Mars/Olympus")


def test_naive_rejected():
    with pytest.raises(ValueError):
        timeutil.ensure_aware(datetime(2026, 1, 1))


@pytest.mark.parametrize("delta,text", [
    (timedelta(minutes=45), "45m"),
    (timedelta(hours=3), "3h"),
    (timedelta(hours=26), "1d 2h"),
    (timedelta(days=2), "2d"),
])
def test_humanize_age(delta, text):
    assert timeutil.humanize_age(delta) == text


def test_format_local():
    dt = datetime(2026, 10, 14, 9, 30, tzinfo=timezone.utc)
    assert timeutil.format_local(dt, "Europe/London") == "Wed 14 Oct 10:30 (Europe/London)"
