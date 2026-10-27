from datetime import datetime, timedelta, timezone

import pytest

from alertd.clock import FakeClock, SystemClock


def test_system_clock_is_aware_utc():
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fake_clock_advances():
    c = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    c.advance(minutes=5, seconds=3)
    assert c.now() == datetime(2026, 1, 1, 0, 5, 3, tzinfo=timezone.utc)


def test_fake_clock_set_converts_to_utc():
    c = FakeClock()
    plus2 = timezone(timedelta(hours=2))
    c.set(datetime(2026, 6, 1, 10, 0, tzinfo=plus2))
    assert c.now() == datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc)


def test_fake_clock_rejects_naive():
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 1, 1))
