from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from calkit.event import Event

PARIS = ZoneInfo("Europe/Paris")
NEW_YORK = ZoneInfo("America/New_York")


@pytest.fixture
def make_event():
    def make(title="Standup", start=None, minutes=30, tz=PARIS, **kw):
        start = start or datetime(2026, 6, 1, 9, 0)
        return Event(title, start.replace(tzinfo=tz), timedelta(minutes=minutes), **kw)

    return make
