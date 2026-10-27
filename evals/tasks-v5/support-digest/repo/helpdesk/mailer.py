"""Outgoing email.

``Mailer`` is the interface; ``FakeMailer`` records what it was asked to send
(``.sent``) and is what the tests use. ``SmtpMailer`` is the production one.
"""

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Optional

from . import config


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str
    sender: str = config.SUPPORT_FROM_ADDRESS
    headers: dict = field(default_factory=dict, compare=False, hash=False)


class MailerError(RuntimeError):
    pass


class Mailer:
    def send(self, email: Email) -> None:
        raise NotImplementedError


class FakeMailer(Mailer):
    def __init__(self, fail_for: Optional[set[str]] = None):
        self.sent: list[Email] = []
        self.fail_for = set(fail_for or ())

    def send(self, email: Email) -> None:
        if email.to in self.fail_for:
            raise MailerError(f"refused: {email.to}")
        self.sent.append(email)

    def to(self, address: str) -> list[Email]:
        return [e for e in self.sent if e.to == address]

    def clear(self) -> None:
        self.sent.clear()


class SmtpMailer(Mailer):
    def __init__(self, host: str = config.SMTP_HOST, port: int = config.SMTP_PORT,
                 username: Optional[str] = None, password: Optional[str] = None):
        self.host, self.port = host, port
        self.username, self.password = username, password

    def send(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = email.sender
        msg["To"] = email.to
        msg["Subject"] = email.subject
        for name, value in email.headers.items():
            msg[name] = value
        msg.set_content(email.body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password or "")
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise MailerError(str(exc)) from exc
