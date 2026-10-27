from datetime import datetime, timezone

import pytest

from helpdesk import assignment, search, workflow
from helpdesk.clock import FakeClock
from helpdesk.queues import STANDARD_QUEUES, Queue, install_standard_queues
from helpdesk.store import InMemoryStore, JsonStore, NotFound

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def test_install_standard_queues_is_idempotent():
    s = InMemoryStore()
    install_standard_queues(s)
    install_standard_queues(s)
    assert [q.id for q in s.list_queues()] == sorted(q.id for q in STANDARD_QUEUES)


def test_open_ticket_in_a_queue(store, clock):
    t = workflow.open_ticket(store, clock, "Invoice wrong", "c@x.example", queue="billing")
    assert t.queue == "billing"
    assert workflow.open_ticket(store, clock, "Login", "c@x.example").queue == "support"


def test_move_to_unknown_queue_fails(store, clock):
    t = workflow.open_ticket(store, clock, "Login", "c@x.example")
    with pytest.raises(NotFound):
        workflow.move_to_queue(store, clock, t.id, "nope")


def test_agent_can_hold_tickets_from_several_queues(store, clock):
    install_standard_queues(store)
    a = workflow.open_ticket(store, clock, "Login", "c@x.example")
    b = workflow.open_ticket(store, clock, "Refund", "c@x.example", queue="billing")
    assignment.assign(store, clock, a.id, "mai")
    assignment.assign(store, clock, b.id, "mai")
    assert {t.queue for t in store.list_tickets(assignee="mai")} == {"support", "billing"}
    assert [t.id for t in store.list_tickets(queue="billing")] == [b.id]


def test_move_to_queue_keeps_assignee(store, clock):
    install_standard_queues(store)
    t = workflow.open_ticket(store, clock, "Broken drill", "c@x.example")
    assignment.assign(store, clock, t.id, "sam")
    workflow.move_to_queue(store, clock, t.id, "hardware")
    assert store.get_ticket(t.id).queue == "hardware"
    assert store.get_ticket(t.id).assignee == "sam"


def test_queues_survive_json_round_trip(tmp_path):
    s = JsonStore(tmp_path / "s.json")
    s.add_queue(Queue("partners", "Partner accounts", muted_in_digest=True))
    again = JsonStore(tmp_path / "s.json")
    assert again.get_queue("partners").muted_in_digest is True


def test_search_by_queue(store, clock):
    install_standard_queues(store)
    workflow.open_ticket(store, clock, "Refund please", "c@x.example", queue="billing")
    workflow.open_ticket(store, clock, "Refund status", "c@x.example")
    q = search.parse("queue:billing refund")
    assert [t.queue for t in search.run(q, store.list_tickets())] == ["billing"]
