from datetime import datetime, timedelta, timezone

from helpdesk import reports, sla
from helpdesk.models import HIGH, OPEN, PENDING_CUSTOMER, RESOLVED, Ticket

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def _tickets():
    return [
        sla.apply_sla(Ticket(id="T-1", subject="a", requester="x", created_at=T0, priority=HIGH, assignee="mai")),
        Ticket(id="T-2", subject="b", requester="x", created_at=T0, status=PENDING_CUSTOMER, assignee="mai"),
        Ticket(id="T-3", subject="c", requester="x", created_at=T0, status=RESOLVED,
               resolved_at=T0 + timedelta(hours=10)),
        Ticket(id="T-4", subject="d", requester="x", created_at=T0, status=RESOLVED,
               resolved_at=T0 + timedelta(hours=30)),
        Ticket(id="T-5", subject="e", requester="x", created_at=T0, status=OPEN),
    ]


def test_backlog():
    b = reports.backlog(_tickets(), T0 + timedelta(hours=5))
    assert b.by_status[RESOLVED] == 2
    assert b.by_assignee == {"mai": 2}
    assert b.breached == 1
    assert b.unassigned == 1


def test_resolved_between():
    got = reports.resolved_between(_tickets(), T0, T0 + timedelta(hours=24))
    assert [t.id for t in got] == ["T-3"]


def test_median_resolution_hours():
    assert reports.median_resolution_hours(_tickets()) == 20.0
