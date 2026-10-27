from datetime import date, datetime, timezone

from meterly import periods


def test_month_period():
    assert periods.month_period(2026, 9) == (date(2026, 9, 1), date(2026, 10, 1))
    assert periods.month_period(2026, 12) == (date(2026, 12, 1), date(2027, 1, 1))


def test_previous_month():
    assert periods.previous_month(date(2026, 1, 14)) == (date(2025, 12, 1), date(2026, 1, 1))


def test_days_in_month():
    assert periods.days_in_month(2027, 2) == 28
    assert periods.days_in_month(2028, 2) == 29
    assert periods.days_in_month(2026, 9) == 30


def test_days():
    assert list(periods.days(date(2026, 9, 29), date(2026, 10, 2))) == [
        date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1)]


def test_local_midnight():
    assert periods.local_midnight(date(2026, 9, 1), "Asia/Tokyo") == datetime(2026, 8, 31, 15, tzinfo=timezone.utc)
    assert periods.local_midnight(date(2026, 9, 1), "UTC") == datetime(2026, 9, 1, tzinfo=timezone.utc)


def test_period_bounds_follow_dst():
    lo, hi = periods.period_bounds_utc(date(2026, 10, 1), date(2026, 11, 1), "Europe/London")
    assert lo == datetime(2026, 9, 30, 23, tzinfo=timezone.utc)
    assert hi == datetime(2026, 11, 1, 0, tzinfo=timezone.utc)


def test_local_date():
    dt = datetime(2026, 9, 30, 20, tzinfo=timezone.utc)
    assert periods.local_date(dt, "Asia/Tokyo") == date(2026, 10, 1)
    assert periods.local_date(dt, "America/Denver") == date(2026, 9, 30)


def test_label():
    assert periods.label(date(2026, 9, 1), date(2026, 10, 1)) == "September 2026"
    assert periods.label(date(2026, 9, 5), date(2026, 9, 12)) == "2026-09-05 to 2026-09-11"
