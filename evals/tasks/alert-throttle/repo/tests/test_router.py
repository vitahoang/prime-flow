import pytest

from alertd.models import Alert, CRITICAL, INFO, WARNING, EMAIL, SMS, SLACK
from alertd.router import NoNotifier, Router


def test_routes_to_channel(notifiers, clock):
    r = Router(notifiers, clock=clock)
    assert r.route(Alert(WARNING, "db", "lag", SMS)) is True
    assert len(notifiers[SMS].sent) == 1
    assert notifiers[EMAIL].sent == [] and notifiers[SLACK].sent == []


def test_log_records_time(notifiers, clock):
    r = Router(notifiers, clock=clock)
    r.route(Alert(INFO, "s", "m", SLACK))
    assert r.log[0].at == clock.now()
    assert r.log[0].delivered


def test_route_many_counts(notifiers, clock):
    r = Router(notifiers, clock=clock)
    alerts = [Alert(INFO, "s", f"m{i}", EMAIL) for i in range(4)]
    assert r.route_many(alerts) == 4
    assert r.delivered() == alerts


def test_missing_notifier(clock):
    r = Router({}, clock=clock)
    with pytest.raises(NoNotifier):
        r.route(Alert(CRITICAL, "s", "m", SMS))
