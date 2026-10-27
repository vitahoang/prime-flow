from datetime import date, datetime, timedelta, timezone

import pytest

from helpdesk.models import (
    PENDING_AGENT, RESOLVED, Agent, OutOfOffice, Ticket,
)

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def test_ticket_defaults():
    t = Ticket(id="T-1", subject="Login broken", requester="a@b.example", created_at=T0)
    assert t.updated_at == T0
    assert t.is_active
    assert t.assignee is None and t.assigned_at is None


def test_ticket_validates_status_and_priority():
    with pytest.raises(ValueError):
        Ticket(id="T-1", subject="x", requester="a@b", created_at=T0, status="closed")
    with pytest.raises(ValueError):
        Ticket(id="T-1", subject="x", requester="a@b", created_at=T0, priority="p1")


def test_resolved_is_not_active():
    t = Ticket(id="T-1", subject="x", requester="a@b", created_at=T0, status=RESOLVED)
    assert not t.is_active


def test_overdue():
    t = Ticket(id="T-1", subject="x", requester="a@b", created_at=T0, status=PENDING_AGENT,
               sla_due_at=T0 + timedelta(hours=4))
    assert not t.is_overdue(T0 + timedelta(hours=3))
    assert t.is_overdue(T0 + timedelta(hours=5))


def test_out_of_office_flag():
    a = Agent(id="a", name="A", email="a@x", out_of_office=True)
    assert a.is_away(date(2026, 10, 12))
    assert not Agent(id="b", name="B", email="b@x").is_away(date(2026, 10, 12))


def test_out_of_office_range():
    a = Agent(id="a", name="A", email="a@x",
              out_of_office=OutOfOffice(date(2026, 10, 10), date(2026, 10, 14)))
    assert a.is_away(date(2026, 10, 12))
    assert not a.is_away(date(2026, 10, 15))
    assert a.out_of_office.days == 5


def test_out_of_office_range_must_be_ordered():
    with pytest.raises(ValueError):
        OutOfOffice(date(2026, 10, 14), date(2026, 10, 10))


def test_first_name():
    assert Agent(id="m", name="Mai Nguyen", email="m@x").first_name() == "Mai"


def test_workdays_default_and_custom():
    a = Agent(id="a", name="A", email="a@x")
    assert a.works_on(date(2026, 10, 16))       # Friday
    assert not a.works_on(date(2026, 10, 17))   # Saturday
    b = Agent(id="b", name="B", email="b@x", workdays=(5, 6, 0, 1, 2))
    assert b.works_on(date(2026, 10, 17))
    assert not b.works_on(date(2026, 10, 15))   # Thursday


def test_event_kind_validated():
    from helpdesk.models import Event
    with pytest.raises(ValueError):
        Event(kind="poke", at=T0)
