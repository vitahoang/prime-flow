"""A Calendar is a named, ordered collection of events."""

from .timeutil import end_of_day, require_aware, start_of_day


class Calendar:
    def __init__(self, name, events=()):
        self.name = name
        self._events = []
        for event in events:
            self.add(event)

    def add(self, event):
        self._events.append(event)
        self._events.sort(key=lambda e: (e.start, e.title))
        return event

    def remove(self, event):
        try:
            self._events.remove(event)
        except ValueError:
            raise KeyError(f"event not in calendar: {event.title!r}") from None

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        return iter(list(self._events))

    def __contains__(self, event):
        return event in self._events

    def between(self, start, end):
        """Events that overlap the half-open window [start, end)."""
        require_aware(start, "window start")
        require_aware(end, "window end")
        found = []
        for event in self._events:
            if event.duration.total_seconds() == 0:
                if start <= event.start < end:
                    found.append(event)
            elif event.start < end and start < event.end:
                found.append(event)
        return found

    def on(self, day, tz):
        """Events that intersect the calendar day ``day`` as seen in ``tz``."""
        return self.between(start_of_day(day, tz), end_of_day(day, tz))

    def find(self, title):
        """Events whose title contains ``title`` (case-insensitive)."""
        needle = title.lower()
        return [e for e in self._events if needle in e.title.lower()]

    def conflicts(self):
        """Pairs of events that overlap each other, in start order."""
        pairs = []
        for i, a in enumerate(self._events):
            for b in self._events[i + 1:]:
                if b.start >= a.end:
                    break
                if a.overlaps(b):
                    pairs.append((a, b))
        return pairs
