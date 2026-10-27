from alertd import formatting
from alertd.models import Alert, CRITICAL, INFO, WARNING, EMAIL, SMS, SLACK


def test_stamp_uses_user_timezone(settings, clock):
    # 09:30 UTC in March is 10:30 in Berlin (CET)
    assert formatting.stamp(clock.now(), settings) == "2026-03-10 10:30 CET"


def test_prefixes():
    assert formatting.prefix(Alert(CRITICAL, "s", "m", SMS)) == "[CRITICAL]"
    assert formatting.prefix(Alert(WARNING, "s", "m", SMS)) == "[warn]"
    assert formatting.prefix(Alert(INFO, "s", "m", SMS)) == "[info]"


def test_sms_is_truncated(settings, clock):
    text = formatting.sms_text(Alert(INFO, "s", "x" * 400, SMS), clock.now(), settings)
    assert len(text) == formatting.SMS_MAX
    assert text.endswith("...")


def test_sms_shows_local_time(settings, clock):
    text = formatting.sms_text(Alert(WARNING, "db", "lag", SMS), clock.now(), settings)
    assert text == "[warn] 10:30 db: lag"


def test_email_body_lists_tags(settings, clock):
    body = formatting.email_body(Alert(INFO, "s", "m", EMAIL, tags=("a", "b")), clock.now(), settings)
    assert "Tags: a, b" in body


def test_slack_text(settings, clock):
    text = formatting.slack_text(Alert(CRITICAL, "api", "5xx spike", SLACK), clock.now(), settings)
    assert text.startswith(":rotating_light: *api*")
