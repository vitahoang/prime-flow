from datetime import date, datetime

import pytest

from calkit.calendar import Calendar
from conftest import PARIS, NEW_YORK


def test_events_are_kept_in_start_order(make_event):
    late = make_event("Late", start=datetime(2026, 6, 1, 17))
    early = make_event("Early", start=datetime(2026, 6, 1, 8))
    cal = Calendar("work", [late, early])
    assert [e.title for e in cal] == ["Early", "Late"]


def test_remove_missing_raises(make_event):
    cal = Calendar("work")
    with pytest.raises(KeyError):
        cal.remove(make_event())


def test_between_is_half_open(make_event):
    e = make_event(minutes=60)
    cal = Calendar("work", [e])
    assert cal.between(e.end, datetime(2026, 6, 2, tzinfo=PARIS)) == []
    assert cal.between(e.start, e.end) == [e]


def test_on_uses_requested_zone(make_event):
    e = make_event(start=datetime(2026, 6, 2, 3, 0))  # 21:00 on June 1 in New York
    cal = Calendar("work", [e])
    assert cal.on(date(2026, 6, 1), NEW_YORK) == [e]
    assert cal.on(date(2026, 6, 1), PARIS) == []


def test_find_is_case_insensitive(make_event):
    cal = Calendar("work", [make_event("Team Standup"), make_event("Lunch")])
    assert [e.title for e in cal.find("standup")] == ["Team Standup"]


def test_conflicts(make_event):
    a = make_event("A", minutes=60)
    b = make_event("B", start=datetime(2026, 6, 1, 9, 30))
    c = make_event("C", start=datetime(2026, 6, 1, 11))
    assert Calendar("work", [a, b, c]).conflicts() == [(a, b)]
