import pytest

from alertd.models import Alert, InvalidAlert, CRITICAL, INFO, WARNING, SMS, severity_rank


def test_alert_fields():
    a = Alert(WARNING, "db-primary", "replication lag 40s", SMS)
    assert a.severity == WARNING
    assert a.channel == SMS
    assert not a.is_critical


def test_critical_flag():
    assert Alert(CRITICAL, "db-primary", "down", SMS).is_critical


@pytest.mark.parametrize("kwargs", [
    dict(severity="fatal", source="x", message="m", channel=SMS),
    dict(severity=INFO, source="x", message="m", channel="pager"),
    dict(severity=INFO, source="", message="m", channel=SMS),
    dict(severity=INFO, source="x", message="", channel=SMS),
])
def test_invalid_alerts_rejected(kwargs):
    with pytest.raises(InvalidAlert):
        Alert(**kwargs)


def test_severity_rank_orders():
    assert severity_rank(INFO) < severity_rank(WARNING) < severity_rank(CRITICAL)


def test_alerts_are_hashable():
    a = Alert(INFO, "x", "m", SMS)
    b = Alert(INFO, "x", "m", SMS)
    assert a == b and len({a, b}) == 1
