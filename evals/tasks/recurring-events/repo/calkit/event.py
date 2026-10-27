"""The Event model.

Every event carries its own IANA timezone: ``start`` must be an aware datetime
whose tzinfo is a ``zoneinfo.ZoneInfo``. Wall-clock times are always shown in
the event's own zone unless a caller asks for another one.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .timeutil import end_of_day, require_aware, start_of_day


@dataclass(frozen=True)
class Event:
    title: str
    start: datetime
    duration: timedelta
    location: str = ""

    def __post_init__(self):
        if not self.title or not self.title.strip():
            raise ValueError("event title must not be empty")
        require_aware(self.start, "event start")
        if not isinstance(self.start.tzinfo, ZoneInfo):
            raise ValueError("event start must use a zoneinfo.ZoneInfo timezone")
        if self.duration < timedelta(0):
            raise ValueError("event duration must not be negative")

    @property
    def tz(self):
        """The event's own timezone."""
        return self.start.tzinfo

    @property
    def end(self):
        return self.start + self.duration

    def overlaps(self, other):
        """True if the two events share any instant (touching ends don't count)."""
        return self.start < other.end and other.start < self.end

    def occurs_on(self, day, tz=None):
        """True if the event intersects ``day`` as seen in ``tz`` (default: its own zone)."""
        tz = tz or self.tz
        lo, hi = start_of_day(day, tz), end_of_day(day, tz)
        if self.duration == timedelta(0):
            return lo <= self.start < hi
        return self.start < hi and lo < self.end

    def moved_to(self, new_start):
        """A copy of this event starting at ``new_start``, same duration."""
        return replace(self, start=new_start)

    def to_dict(self):
        return {
            "title": self.title,
            "start": self.start.replace(tzinfo=None).isoformat(),
            "tz": self.tz.key,
            "duration_minutes": int(self.duration.total_seconds() // 60),
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, data):
        tz = ZoneInfo(data["tz"])
        start = datetime.fromisoformat(data["start"]).replace(tzinfo=tz)
        return cls(
            title=data["title"],
            start=start,
            duration=timedelta(minutes=data["duration_minutes"]),
            location=data.get("location", ""),
        )
