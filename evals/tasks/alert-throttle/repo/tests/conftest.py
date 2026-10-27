from datetime import datetime, timezone

import pytest

from alertd.clock import FakeClock
from alertd.notifiers import build_notifiers
from alertd.settings import UserSettings


@pytest.fixture
def settings():
    return UserSettings(
        user_id="dana",
        timezone="Europe/Berlin",
        email="dana@example.com",
        phone="+4915100000000",
        slack_handle="@dana",
    )


@pytest.fixture
def clock():
    return FakeClock(datetime(2026, 3, 10, 9, 30, tzinfo=timezone.utc))


@pytest.fixture
def notifiers(settings):
    return build_notifiers(settings)
