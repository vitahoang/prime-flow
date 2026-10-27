from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

import pytest

from calkit.event import Event

PARIS = ZoneInfo("Europe/Paris")


def test_end_is_start_plus_duration(make_event):
    e = make_event(minutes=45)
    assert e.end == datetime(2026, 6, 1, 9, 45, tzinfo=PARIS)


def test_tz_is_events_own_zone(make_event):
    assert make_event(tz=ZoneInfo("Asia/Tokyo")).tz.key == "Asia/Tokyo"


def test_naive_start_rejected():
    with pytest.raises(ValueError):
        Event("x", datetime(2026, 6, 1, 9), timedelta(minutes=5))


def test_fixed_offset_rejected():
    with pytest.raises(ValueError):
        Event("x", datetime(2026, 6, 1, 9, tzinfo=timezone.utc), timedelta(minutes=5))


def test_empty_title_rejected():
    with pytest.raises(ValueError):
        Event("  ", datetime(2026, 6, 1, 9, tzinfo=PARIS), timedelta(minutes=5))


def test_negative_duration_rejected():
    with pytest.raises(ValueError):
        Event("x", datetime(2026, 6, 1, 9, tzinfo=PARIS), timedelta(minutes=-1))


def test_overlaps(make_event):
    a = make_event(minutes=60)
    b = make_event(start=datetime(2026, 6, 1, 9, 30))
    c = make_event(start=datetime(2026, 6, 1, 10, 0))
    assert a.overlaps(b) and b.overlaps(a)
    assert not a.overlaps(c)


def test_occurs_on_uses_own_zone_by_default(make_event):
    e = make_event(start=datetime(2026, 6, 1, 23, 30), minutes=15)
    assert e.occurs_on(date(2026, 6, 1))
    assert e.occurs_on(date(2026, 6, 1), ZoneInfo("America/New_York"))
    assert not e.occurs_on(date(2026, 6, 2))


def test_round_trip_dict(make_event):
    e = make_event(location="Room 2")
    assert Event.from_dict(e.to_dict()) == e


def test_moved_to_keeps_duration(make_event):
    e = make_event(minutes=20)
    moved = e.moved_to(datetime(2026, 6, 2, 8, tzinfo=PARIS))
    assert moved.duration == e.duration and moved.title == e.title
