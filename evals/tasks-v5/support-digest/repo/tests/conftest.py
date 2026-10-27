from datetime import datetime, timezone

import pytest

from helpdesk.clock import FakeClock
from helpdesk.mailer import FakeMailer
from helpdesk.models import Agent
from helpdesk.store import InMemoryStore

START = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)  # a Monday


@pytest.fixture
def clock():
    return FakeClock(START)


@pytest.fixture
def mailer():
    return FakeMailer()


@pytest.fixture
def store():
    s = InMemoryStore()
    s.add_agent(Agent(id="mai", name="Mai Nguyen", email="mai@acme.example", timezone="Asia/Ho_Chi_Minh"))
    s.add_agent(Agent(id="sam", name="Sam Ortiz", email="sam@acme.example", timezone="America/Los_Angeles"))
    s.add_agent(Agent(id="priya", name="Priya Shah", email="priya@acme.example", timezone="Europe/London"))
    return s
