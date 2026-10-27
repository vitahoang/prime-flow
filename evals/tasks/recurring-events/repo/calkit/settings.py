"""Library-wide settings.

These are plain module attributes so callers can override them at start-up,
e.g. ``calkit.settings.WEEK_START = 6`` for Sunday-first weeks.
"""

# First day of the week for week-based views, numbered like
# ``datetime.date.weekday()`` (Monday == 0 ... Sunday == 6).
WEEK_START = 0

# Format used when rendering times in views and agendas.
TIME_FORMAT = "%H:%M"

# Format used when rendering dates in views and agendas.
DATE_FORMAT = "%a %Y-%m-%d"
