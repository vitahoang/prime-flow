"""Turn alerts into channel-specific text."""

from datetime import datetime

from .models import Alert, CRITICAL, WARNING
from .settings import UserSettings

SMS_MAX = 160


def local_time(when: datetime, settings: UserSettings) -> datetime:
    """Convert an aware UTC datetime into the user's own timezone."""
    return when.astimezone(settings.tz)


def stamp(when: datetime, settings: UserSettings) -> str:
    return local_time(when, settings).strftime("%Y-%m-%d %H:%M %Z")


def prefix(alert: Alert) -> str:
    if alert.severity == CRITICAL:
        return "[CRITICAL]"
    if alert.severity == WARNING:
        return "[warn]"
    return "[info]"


def email_subject(alert: Alert) -> str:
    return f"{prefix(alert)} {alert.source}: {alert.message[:60]}"


def email_body(alert: Alert, when: datetime, settings: UserSettings) -> str:
    lines = [
        f"Source:   {alert.source}",
        f"Severity: {alert.severity}",
        f"Time:     {stamp(when, settings)}",
        "",
        alert.message,
    ]
    if alert.tags:
        lines += ["", "Tags: " + ", ".join(alert.tags)]
    return "\n".join(lines)


def sms_text(alert: Alert, when: datetime, settings: UserSettings) -> str:
    hhmm = local_time(when, settings).strftime("%H:%M")
    text = f"{prefix(alert)} {hhmm} {alert.source}: {alert.message}"
    if len(text) > SMS_MAX:
        text = text[: SMS_MAX - 3] + "..."
    return text


def slack_text(alert: Alert, when: datetime, settings: UserSettings) -> str:
    emoji = {CRITICAL: ":rotating_light:", WARNING: ":warning:"}.get(alert.severity, ":information_source:")
    return f"{emoji} *{alert.source}* ({stamp(when, settings)})\n{alert.message}"
