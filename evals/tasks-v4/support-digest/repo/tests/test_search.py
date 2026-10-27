from datetime import datetime, timedelta, timezone

from helpdesk import search
from helpdesk.models import HIGH, LOW, OPEN, PENDING_AGENT, URGENT, Ticket

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def _tickets():
    return [
        Ticket(id="T-1", subject="Refund for order", requester="a@x", created_at=T0, priority=LOW, assignee="mai"),
        Ticket(id="T-2", subject="Login loop", requester="b@x", created_at=T0 + timedelta(hours=1),
               priority=URGENT, status=PENDING_AGENT, tags=["vip"]),
        Ticket(id="T-3", subject="refund again", requester="c@x", created_at=T0 + timedelta(hours=2),
               priority=HIGH, assignee="sam"),
    ]


def test_parse_and_run():
    q = search.parse("refund assignee:sam")
    assert [t.id for t in search.run(q, _tickets())] == ["T-3"]


def test_unassigned_and_status():
    q = search.parse("is:unassigned status:pending_agent,open")
    assert [t.id for t in search.run(q, _tickets())] == ["T-2"]


def test_tag_and_created_after():
    q = search.Query(tag="vip", created_after=T0)
    assert [t.id for t in search.run(q, _tickets())] == ["T-2"]


def test_by_priority():
    assert [t.id for t in search.by_priority(_tickets())] == ["T-2", "T-3", "T-1"]


def test_extra_predicate():
    q = search.Query(statuses={OPEN}, extra=[lambda t: t.assignee == "mai"])
    assert [t.id for t in search.run(q, _tickets())] == ["T-1"]
