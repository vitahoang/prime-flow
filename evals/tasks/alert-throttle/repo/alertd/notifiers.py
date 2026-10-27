"""Notifiers deliver formatted alerts to one channel.

The real transports (SMTP, the SMS gateway, the Slack webhook) are not wired up
yet; each notifier records what it would have sent in ``.sent`` so the rest of
the system can be built and tested against them.
"""

from dataclasses import dataclass
from datetime import datetime

from . import formatting
from .models import Alert, EMAIL, SMS, SLACK
from .settings import UserSettings


@dataclass(frozen=True)
class Sent:
    alert: Alert
    at: datetime
    to: str
    text: str


class Notifier:
    channel: str = ""

    def __init__(self, settings: UserSettings):
        self.settings = settings
        self.sent: list[Sent] = []

    def address(self) -> str:
        raise NotImplementedError

    def render(self, alert: Alert, when: datetime) -> str:
        raise NotImplementedError

    def send(self, alert: Alert, when: datetime) -> Sent:
        if alert.channel != self.channel:
            raise ValueError(f"{type(self).__name__} cannot send a {alert.channel} alert")
        record = Sent(alert=alert, at=when, to=self.address(), text=self.render(alert, when))
        self.sent.append(record)
        return record


class EmailNotifier(Notifier):
    channel = EMAIL

    def address(self) -> str:
        return self.settings.email

    def render(self, alert: Alert, when: datetime) -> str:
        subject = formatting.email_subject(alert)
        body = formatting.email_body(alert, when, self.settings)
        return f"Subject: {subject}\n\n{body}"


class SmsNotifier(Notifier):
    channel = SMS

    def address(self) -> str:
        return self.settings.phone

    def render(self, alert: Alert, when: datetime) -> str:
        return formatting.sms_text(alert, when, self.settings)


class SlackNotifier(Notifier):
    channel = SLACK

    def address(self) -> str:
        return self.settings.slack_handle

    def render(self, alert: Alert, when: datetime) -> str:
        return formatting.slack_text(alert, when, self.settings)


def build_notifiers(settings: UserSettings) -> dict[str, Notifier]:
    """One notifier per channel, keyed by channel name."""
    return {
        EMAIL: EmailNotifier(settings),
        SMS: SmsNotifier(settings),
        SLACK: SlackNotifier(settings),
    }
