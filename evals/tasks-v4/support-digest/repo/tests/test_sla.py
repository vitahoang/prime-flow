from datetime import datetime, timedelta, timezone

from helpdesk import sla
from helpdesk.models import HIGH, RESOLVED, URGENT, Ticket

T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def _t(priority, **kw):
    return sla.apply_sla(Ticket(id="T-1", subject="x", requester="c@x", created_at=T0, priority=priority, **kw))


def test_due_at_by_priority():
    assert _t(URGENT).sla_due_at == T0 + timedelta(hours=1)
    assert _t(HIGH).sla_due_at == T0 + timedelta(hours=4)


def test_at_risk_and_breached():
    t = _t(HIGH)
    assert not sla.is_at_risk(t, T0 + timedelta(hours=2))
    assert sla.is_at_risk(t, T0 + timedelta(hours=3, minutes=30))
    assert not sla.is_breached(t, T0 + timedelta(hours=3, minutes=30))
    assert sla.is_breached(t, T0 + timedelta(hours=5))


def test_resolved_never_breaches():
    t = _t(URGENT, status=RESOLVED)
    assert not sla.is_breached(t, T0 + timedelta(days=3))
    assert not sla.is_at_risk(t, T0 + timedelta(minutes=50))


def test_business_hours_between():
    # Monday 08:00 -> 18:00 counts 09:00-17:00 only.
    start = datetime(2026, 10, 12, 8, 0, tzinfo=timezone.utc)
    assert sla.business_hours_between(start, start + timedelta(hours=10)) == 8
    # Saturday counts nothing.
    sat = datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)
    assert sla.business_hours_between(sat, sat + timedelta(hours=4)) == 0
