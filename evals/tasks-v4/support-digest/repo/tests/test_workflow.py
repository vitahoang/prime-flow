from datetime import timedelta

import pytest

from helpdesk import workflow
from helpdesk.models import OPEN, PENDING_AGENT, PENDING_CUSTOMER, RESOLVED


def test_open_ticket_sets_sla_and_id(store, clock):
    t = workflow.open_ticket(store, clock, "Refund please", "c@x.example", body="I was double charged")
    assert t.id == "T-1001"
    assert t.status == OPEN
    assert t.sla_due_at == clock.now() + timedelta(hours=24)
    assert t.comments[0].author == "c@x.example"


def test_agent_reply_moves_to_pending_customer_and_touches(store, clock):
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example")
    clock.advance(hours=2)
    t = workflow.agent_reply(store, clock, t.id, "mai", "Looking into it")
    assert t.status == PENDING_CUSTOMER
    assert t.updated_at == clock.now()


def test_customer_reply_moves_to_pending_agent(store, clock):
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example")
    workflow.agent_reply(store, clock, t.id, "mai", "Which order?")
    clock.advance(hours=5)
    t = workflow.customer_reply(store, clock, t.id, "Order 991")
    assert t.status == PENDING_AGENT
    assert t.updated_at == clock.now()
    assert workflow.waiting_since(t) == clock.now()


def test_customer_reply_reopens_resolved(store, clock):
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example")
    workflow.agent_reply(store, clock, t.id, "mai", "Done", resolve=True)
    assert store.get_ticket(t.id).resolved_at == clock.now()
    clock.advance(days=1)
    t = workflow.customer_reply(store, clock, t.id, "Still broken")
    assert t.status == PENDING_AGENT
    assert t.resolved_at is None


def test_invalid_transition(store, clock):
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example")
    workflow.change_status(store, clock, t.id, RESOLVED)
    with pytest.raises(workflow.InvalidTransition):
        workflow.change_status(store, clock, t.id, PENDING_CUSTOMER)


def test_internal_note_is_private(store, clock):
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example", body="hi")
    clock.advance(minutes=10)
    t = workflow.internal_note(store, clock, t.id, "mai", "customer is a VIP")
    assert t.comments[-1].public is False
    assert workflow.last_public_comment(t).body == "hi"
    assert t.updated_at == clock.now()


def test_events_trail(store, clock):
    from helpdesk import assignment
    from helpdesk.models import AGENT_REPLY, ASSIGNED, CREATED, CUSTOMER_REPLY, INTERNAL_NOTE, STATUS_CHANGED
    t = workflow.open_ticket(store, clock, "Refund", "c@x.example")
    clock.advance(minutes=5)
    assignment.assign(store, clock, t.id, "mai")
    clock.advance(minutes=5)
    workflow.agent_reply(store, clock, t.id, "mai", "Which order?")
    clock.advance(hours=1)
    workflow.customer_reply(store, clock, t.id, "Order 991")
    clock.advance(hours=1)
    t = workflow.internal_note(store, clock, t.id, "mai", "checking with billing")
    kinds = [e.kind for e in t.events]
    assert kinds == [CREATED, ASSIGNED, AGENT_REPLY, STATUS_CHANGED, CUSTOMER_REPLY, STATUS_CHANGED, INTERNAL_NOTE]
    assert t.updated_at == t.events[-1].at == clock.now()
