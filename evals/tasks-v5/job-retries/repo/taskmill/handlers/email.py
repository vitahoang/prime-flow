"""``email.send``: send one plain-text email over SMTP.

Payload: ``{"to": "...", "subject": "...", "body": "..."}``, optionally
``"reply_to"``. Settings come from the ``[email]`` section of the config.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Callable

from .. import config as config_mod
from ..registry import Registry

log = logging.getLogger("taskmill.handlers.email")

REQUIRED = ("to", "subject", "body")

# Tests swap this out; production builds a real SMTP connection.
Transport = Callable[[EmailMessage, config_mod.EmailSettings], None]


def smtp_transport(msg: EmailMessage, settings: config_mod.EmailSettings) -> None:
    with smtplib.SMTP(settings.host, settings.port, timeout=30) as smtp:
        smtp.send_message(msg)


_transport: Transport = smtp_transport


def set_transport(fn: Transport) -> Transport:
    global _transport
    old, _transport = _transport, fn
    return old


def build_message(payload: dict[str, Any], settings: config_mod.EmailSettings) -> EmailMessage:
    missing = [k for k in REQUIRED if not payload.get(k)]
    if missing:
        raise ValueError(f"email.send payload is missing {', '.join(missing)}")
    msg = EmailMessage()
    msg["From"] = settings.sender
    msg["To"] = payload["to"]
    msg["Subject"] = payload["subject"]
    if payload.get("reply_to"):
        msg["Reply-To"] = payload["reply_to"]
    msg.set_content(payload["body"])
    return msg


def send_email(payload: dict[str, Any]) -> None:
    settings = config_mod.load().email
    msg = build_message(payload, settings)
    if settings.dry_run:
        log.info("dry run: would send %r to %s", msg["Subject"], msg["To"])
        return
    _transport(msg, settings)
    log.info("sent %r to %s", msg["Subject"], msg["To"])


def register(registry: Registry) -> None:
    registry.register("email.send", send_email)
