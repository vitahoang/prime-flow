# calkit

A small calendar library on top of the standard library (`zoneinfo`, `datetime`).
No third-party dependencies.

## Model

- `calkit.event.Event(title, start, duration, location="")` — `start` is an aware
  `datetime` whose tzinfo is a `zoneinfo.ZoneInfo`. Every event carries its own
  IANA timezone; `event.tz` returns it.
- `calkit.calendar.Calendar(name, events=())` — ordered collection with
  `between(start, end)`, `on(day, tz)`, `find(title)` and `conflicts()`.

## Views

- `calkit.views.week_of(day)` / `week_view(calendar, day, tz)` — weeks start on
  `calkit.settings.WEEK_START` (Monday by default).
- `calkit.views.agenda(calendar, first, days, tz)`.
- `calkit.formatting.format_event(event)` and `render_week(view, tz)`.

## Development

    python -m pytest
