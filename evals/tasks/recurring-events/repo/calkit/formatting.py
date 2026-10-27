"""Plain-text rendering of events and views."""

from . import settings


def format_time(dt, tz=None):
    if tz is not None:
        dt = dt.astimezone(tz)
    return dt.strftime(settings.TIME_FORMAT)


def format_event(event, tz=None):
    """``"Mon 2026-06-01 09:00-10:00 Standup @ Room 2 (Europe/Paris)"``."""
    tz = tz or event.tz
    start = event.start.astimezone(tz)
    text = (
        f"{start.strftime(settings.DATE_FORMAT)} "
        f"{format_time(start)}-{format_time(event.end, tz)} {event.title}"
    )
    if event.location:
        text += f" @ {event.location}"
    return f"{text} ({tz.key})"


def render_week(view, tz):
    """Render the dict returned by ``views.week_view`` as text, one block per day."""
    lines = []
    for day, events in view.items():
        lines.append(day.strftime(settings.DATE_FORMAT))
        if not events:
            lines.append("  (nothing)")
        for event in events:
            lines.append(
                f"  {format_time(event.start, tz)} {event.title}"
            )
    return "\n".join(lines)
