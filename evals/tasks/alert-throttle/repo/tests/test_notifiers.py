import pytest

from alertd.models import Alert, INFO, EMAIL, SMS, SLACK


def test_each_channel_has_a_notifier(notifiers):
    assert set(notifiers) == {EMAIL, SMS, SLACK}


def test_send_records(notifiers, clock):
    rec = notifiers[SMS].send(Alert(INFO, "s", "hello", SMS), clock.now())
    assert notifiers[SMS].sent == [rec]
    assert rec.to == "+4915100000000"


def test_email_render_has_subject(notifiers, clock):
    rec = notifiers[EMAIL].send(Alert(INFO, "s", "hello", EMAIL), clock.now())
    assert rec.text.startswith("Subject: [info] s: hello")


def test_wrong_channel_rejected(notifiers, clock):
    with pytest.raises(ValueError):
        notifiers[SLACK].send(Alert(INFO, "s", "m", SMS), clock.now())
