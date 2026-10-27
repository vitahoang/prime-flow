"""Calendar views: a week grid and a rolling agenda."""

from datetime import timedelta

from .timeutil import iter_days, start_of_week


def week_of(day, week_start=None):
    """The seven dates of the week containing ``day``, honouring ``settings.WEEK_START``."""
    first = start_of_week(day, week_start)
    return [first + timedelta(days=i) for i in range(7)]


def week_view(calendar, day, tz, week_start=None):
    """Map each date of ``day``'s week to the events on that date in ``tz``."""
    return {d: calendar.on(d, tz) for d in week_of(day, week_start)}


def agenda(calendar, first, days, tz):
    """``(date, events)`` pairs for ``days`` consecutive days, skipping empty days."""
    last = first + timedelta(days=days - 1)
    rows = []
    for d in iter_days(first, last):
        events = calendar.on(d, tz)
        if events:
            rows.append((d, events))
    return rows
