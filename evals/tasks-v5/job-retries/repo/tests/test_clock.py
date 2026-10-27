import pytest

from taskmill.clock import EPOCH_2026, FakeClock, format_ts, parse_ts


def test_fake_clock_moves_only_when_told():
    c = FakeClock()
    assert c.now() == EPOCH_2026
    c.advance(90)
    assert c.now() == EPOCH_2026 + 90
    c.sleep(10)
    assert c.now() == EPOCH_2026 + 100
    assert c.sleeps == [10]


def test_fake_clock_never_goes_back():
    c = FakeClock(100)
    with pytest.raises(ValueError):
        c.advance(-1)
    with pytest.raises(ValueError):
        c.set(50)


def test_format_and_parse_round_trip():
    assert format_ts(EPOCH_2026) == "2026-01-01 00:00:00"
    assert parse_ts("2026-01-01T00:00:00Z") == EPOCH_2026
    assert parse_ts("2026-01-01") == EPOCH_2026
    assert format_ts(None) == "-"
