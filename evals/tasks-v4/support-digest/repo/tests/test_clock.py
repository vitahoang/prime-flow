from datetime import datetime, timedelta, timezone

import pytest

from helpdesk.clock import FakeClock, SystemClock


def test_system_clock_is_aware_utc():
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_fake_clock_advances():
    c = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    c.advance(minutes=15)
    assert c.now() == datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)


def test_fake_clock_rejects_naive_and_backwards():
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 1, 1))
    c = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError):
        c.advance(minutes=-1)


def test_fake_clock_set_converts_to_utc():
    c = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    c.set(datetime(2026, 1, 1, 9, 0, tzinfo=timezone(timedelta(hours=7))))
    assert c.now() == datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
