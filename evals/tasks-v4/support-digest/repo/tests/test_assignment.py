from datetime import date, timedelta

import pytest

from helpdesk import assignment, workflow
from helpdesk.models import OutOfOffice


def test_assign_sets_assigned_at(store, clock):
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    clock.advance(hours=3)
    t = assignment.assign(store, clock, t.id, "mai")
    assert t.assignee == "mai"
    assert t.assigned_at == clock.now()
    assert t.created_at == clock.now() - timedelta(hours=3)


def test_assign_same_agent_is_noop(store, clock):
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    assignment.assign(store, clock, t.id, "mai")
    first = store.get_ticket(t.id).assigned_at
    clock.advance(hours=1)
    assignment.assign(store, clock, t.id, "mai")
    assert store.get_ticket(t.id).assigned_at == first


def test_unassign(store, clock):
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    assignment.assign(store, clock, t.id, "mai")
    t = assignment.unassign(store, clock, t.id)
    assert t.assignee is None and t.assigned_at is None


def test_auto_assign_least_loaded(store, clock):
    for _ in range(2):
        t = workflow.open_ticket(store, clock, "x", "c@x.example")
        assignment.assign(store, clock, t.id, "mai")
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    assignment.assign(store, clock, t.id, "priya")
    new = workflow.open_ticket(store, clock, "y", "c@x.example")
    assert assignment.auto_assign(store, clock, new.id).assignee == "sam"


def test_auto_assign_skips_out_of_office(store, clock):
    sam = store.get_agent("sam")
    sam.out_of_office = True
    store.save_agent(sam)
    mai = store.get_agent("mai")
    mai.out_of_office = OutOfOffice(date(2026, 10, 10), date(2026, 10, 16))
    store.save_agent(mai)
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    assert assignment.auto_assign(store, clock, t.id).assignee == "priya"


def test_out_of_office_range_checked_in_agent_timezone(store, clock):
    # 2026-10-12 20:00 UTC is already the 13th in Ho Chi Minh City.
    clock.set(clock.now().replace(hour=20))
    for agent_id in ("sam", "priya"):
        a = store.get_agent(agent_id)
        a.out_of_office = True
        store.save_agent(a)
    mai = store.get_agent("mai")
    mai.out_of_office = OutOfOffice(date(2026, 10, 13), date(2026, 10, 14))
    store.save_agent(mai)
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    with pytest.raises(assignment.NoAgentAvailable):
        assignment.auto_assign(store, clock, t.id)


def test_skill_tag(store, clock):
    priya = store.get_agent("priya")
    priya.skills = ["billing"]
    store.save_agent(priya)
    t = workflow.open_ticket(store, clock, "invoice wrong", "c@x.example", tags=["skill:billing"])
    assert assignment.auto_assign(store, clock, t.id).assignee == "priya"


def test_rebalance_moves_tickets_off_away_agents(store, clock, mailer):
    t = workflow.open_ticket(store, clock, "x", "c@x.example")
    assignment.assign(store, clock, t.id, "sam")
    sam = store.get_agent("sam")
    sam.out_of_office = True
    store.save_agent(sam)
    moved = assignment.rebalance(store, clock, mailer=mailer)
    assert [m.id for m in moved] == [t.id]
    assert store.get_ticket(t.id).assignee in {"mai", "priya"}
    assert len(mailer.sent) == 1
