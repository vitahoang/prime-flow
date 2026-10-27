from datetime import timedelta

from helpdesk import assignment, workflow
from helpdesk.mailer import FakeMailer
from helpdesk.models import HIGH
from helpdesk.notifications import ASSIGNMENT, SLA_WARNING, notify_assignment, send_sla_warnings
from helpdesk.store import JsonStore


def test_assignment_email(store, clock, mailer):
    t = workflow.open_ticket(store, clock, "Printer on fire", "c@x.example")
    assignment.assign(store, clock, t.id, "priya", mailer=mailer)
    assert len(mailer.sent) == 1
    email = mailer.sent[0]
    assert email.to == "priya@acme.example"
    assert t.id in email.subject
    assert "Hi Priya" in email.body
    assert "(Europe/London)" in email.body
    assert store.notifications(kind=ASSIGNMENT, agent_id="priya")[0].ticket_id == t.id


def test_assignment_email_not_repeated(store, clock, mailer):
    t = workflow.open_ticket(store, clock, "Printer on fire", "c@x.example")
    assignment.assign(store, clock, t.id, "priya", mailer=mailer)
    assert notify_assignment(store, mailer, clock, store.get_ticket(t.id)) is False
    assert len(mailer.sent) == 1


def test_reassignment_sends_again(store, clock, mailer):
    t = workflow.open_ticket(store, clock, "Printer on fire", "c@x.example")
    assignment.assign(store, clock, t.id, "priya", mailer=mailer)
    clock.advance(hours=1)
    assignment.assign(store, clock, t.id, "mai", mailer=mailer)
    clock.advance(hours=1)
    assignment.assign(store, clock, t.id, "priya", mailer=mailer)
    assert [e.to for e in mailer.sent] == ["priya@acme.example", "mai@acme.example", "priya@acme.example"]


def test_failed_send_is_not_logged(store, clock):
    mailer = FakeMailer(fail_for={"priya@acme.example"})
    t = workflow.open_ticket(store, clock, "Printer on fire", "c@x.example")
    assignment.assign(store, clock, t.id, "priya", mailer=mailer)
    assert store.notifications(kind=ASSIGNMENT) == []


def test_sla_warning_once(store, clock, mailer):
    t = workflow.open_ticket(store, clock, "VPN down", "c@x.example", priority=HIGH)
    assignment.assign(store, clock, t.id, "sam")
    clock.advance(hours=3, minutes=10)
    assert send_sla_warnings(store, mailer, clock) == 1
    clock.advance(minutes=15)
    assert send_sla_warnings(store, mailer, clock) == 0
    assert len(store.notifications(kind=SLA_WARNING)) == 1


def test_sla_warning_dedupe_survives_restart(tmp_path, clock, mailer):
    from helpdesk.models import Agent
    path = tmp_path / "s.json"
    s = JsonStore(path)
    s.add_agent(Agent(id="sam", name="Sam", email="sam@x"))
    t = workflow.open_ticket(s, clock, "VPN down", "c@x.example", priority=HIGH)
    assignment.assign(s, clock, t.id, "sam")
    clock.advance(hours=3, minutes=10)
    assert send_sla_warnings(s, mailer, clock) == 1
    clock.advance(minutes=15)
    assert send_sla_warnings(JsonStore(path), mailer, clock) == 0
