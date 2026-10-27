from datetime import date, datetime, timedelta, timezone

import pytest

from helpdesk.models import Agent, Comment, OutOfOffice, PENDING_AGENT, Ticket
from helpdesk.store import InMemoryStore, JsonStore, NotFound, Notification

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def _ticket(id_, **kw):
    return Ticket(id=id_, subject=f"subject {id_}", requester="c@x.example", created_at=T0, **kw)


def test_add_and_get():
    s = InMemoryStore()
    s.add_ticket(_ticket("T-1001"))
    assert s.get_ticket("T-1001").subject == "subject T-1001"
    with pytest.raises(NotFound):
        s.get_ticket("T-9")


def test_duplicate_ids_rejected():
    s = InMemoryStore()
    s.add_ticket(_ticket("T-1001"))
    with pytest.raises(ValueError):
        s.add_ticket(_ticket("T-1001"))


def test_list_filters():
    s = InMemoryStore()
    s.add_ticket(_ticket("T-1001", assignee="mai"))
    s.add_ticket(_ticket("T-1002", assignee="sam", status=PENDING_AGENT))
    assert [t.id for t in s.list_tickets(assignee="mai")] == ["T-1001"]
    assert [t.id for t in s.list_tickets(status=PENDING_AGENT)] == ["T-1002"]


def test_next_ticket_id():
    s = InMemoryStore()
    assert s.next_ticket_id() == "T-1001"
    s.add_ticket(_ticket("T-1007"))
    assert s.next_ticket_id() == "T-1008"


def test_notification_log_filters():
    s = InMemoryStore()
    s.record_notification(Notification(kind="assignment", agent_id="mai", sent_at=T0, ticket_id="T-1"))
    s.record_notification(Notification(kind="sla_warning", agent_id="mai", sent_at=T0, ticket_id="T-1"))
    s.record_notification(Notification(kind="assignment", agent_id="sam", sent_at=T0, ticket_id="T-2"))
    assert len(s.notifications(kind="assignment")) == 2
    assert len(s.notifications(agent_id="mai")) == 2
    assert len(s.notifications(kind="assignment", agent_id="sam")) == 1


def test_json_store_round_trip(tmp_path):
    path = tmp_path / "store.json"
    s = JsonStore(path)
    s.add_agent(Agent(id="mai", name="Mai Nguyen", email="mai@x", timezone="Asia/Ho_Chi_Minh",
                      out_of_office=OutOfOffice(date(2026, 10, 20), date(2026, 10, 24))))
    s.add_agent(Agent(id="sam", name="Sam", email="sam@x", out_of_office=True, backup_id="mai",
                      workdays=(5, 6, 0, 1, 2)))
    t = _ticket("T-1001", assignee="mai", assigned_at=T0 + timedelta(hours=1),
                updated_at=T0 + timedelta(hours=2))
    t.comments.append(Comment(author="c@x.example", body="help", at=T0))
    t.log("customer_reply", T0 + timedelta(hours=2), "c@x.example")
    s.add_ticket(t)
    s.record_notification(Notification(kind="assignment", agent_id="mai", sent_at=T0, ticket_id="T-1001", key="k"))

    again = JsonStore(path)
    mai = again.get_agent("mai")
    assert mai.timezone == "Asia/Ho_Chi_Minh"
    assert mai.out_of_office == OutOfOffice(date(2026, 10, 20), date(2026, 10, 24))
    sam = again.get_agent("sam")
    assert sam.out_of_office is True and sam.backup_id == "mai" and sam.workdays == (5, 6, 0, 1, 2)
    assert again.get_agent("mai").workdays == (0, 1, 2, 3, 4)
    t2 = again.get_ticket("T-1001")
    assert t2.assigned_at == T0 + timedelta(hours=1)
    assert t2.updated_at == T0 + timedelta(hours=2)
    assert t2.comments[0].body == "help"
    assert [(e.kind, e.at) for e in t2.events] == [("customer_reply", T0 + timedelta(hours=2))]
    assert again.notifications(kind="assignment")[0].key == "k"


def test_json_store_saves_on_every_change(tmp_path):
    path = tmp_path / "store.json"
    s = JsonStore(path)
    s.add_ticket(_ticket("T-1001"))
    t = s.get_ticket("T-1001")
    t.status = PENDING_AGENT
    s.save_ticket(t)
    assert JsonStore(path).get_ticket("T-1001").status == PENDING_AGENT
