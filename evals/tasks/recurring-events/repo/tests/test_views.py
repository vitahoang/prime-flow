from datetime import date, datetime

from calkit import settings
from calkit.calendar import Calendar
from calkit.formatting import format_event, render_week
from calkit.views import agenda, week_of, week_view
from conftest import PARIS


def test_week_starts_on_monday_by_default():
    assert settings.WEEK_START == 0
    days = week_of(date(2026, 6, 4))  # a Thursday
    assert days[0] == date(2026, 6, 1) and days[-1] == date(2026, 6, 7)


def test_week_start_override():
    assert week_of(date(2026, 6, 4), week_start=6)[0] == date(2026, 5, 31)


def test_week_view_groups_by_day(make_event):
    e = make_event(start=datetime(2026, 6, 3, 9))
    view = week_view(Calendar("w", [e]), date(2026, 6, 1), PARIS)
    assert len(view) == 7
    assert view[date(2026, 6, 3)] == [e]
    assert view[date(2026, 6, 2)] == []


def test_agenda_skips_empty_days(make_event):
    e = make_event(start=datetime(2026, 6, 3, 9))
    rows = agenda(Calendar("w", [e]), date(2026, 6, 1), 7, PARIS)
    assert rows == [(date(2026, 6, 3), [e])]


def test_format_event(make_event):
    e = make_event(location="Room 2")
    assert format_event(e) == "Mon 2026-06-01 09:00-09:30 Standup @ Room 2 (Europe/Paris)"


def test_render_week(make_event):
    e = make_event()
    text = render_week(week_view(Calendar("w", [e]), date(2026, 6, 1), PARIS), PARIS)
    assert text.splitlines()[:2] == ["Mon 2026-06-01", "  09:00 Standup"]
