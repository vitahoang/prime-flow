import pytest

from helpdesk.mailer import Email, FakeMailer, MailerError


def test_fake_mailer_records():
    m = FakeMailer()
    m.send(Email(to="a@x", subject="s", body="b"))
    assert m.sent == [Email(to="a@x", subject="s", body="b")]
    assert m.to("a@x")[0].subject == "s"


def test_fake_mailer_can_fail():
    m = FakeMailer(fail_for={"bad@x"})
    with pytest.raises(MailerError):
        m.send(Email(to="bad@x", subject="s", body="b"))
    assert m.sent == []


def test_default_sender():
    assert Email(to="a@x", subject="s", body="b").sender.startswith("support@")
