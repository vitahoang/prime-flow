"""Core alert types."""

from dataclasses import dataclass, field

# Severities, lowest to highest.
INFO = "info"
WARNING = "warning"
CRITICAL = "critical"

SEVERITIES = (INFO, WARNING, CRITICAL)

# Delivery channels.
EMAIL = "email"
SMS = "sms"
SLACK = "slack"

CHANNELS = (EMAIL, SMS, SLACK)


class InvalidAlert(ValueError):
    """Raised when an alert is built with an unknown severity or channel."""


@dataclass(frozen=True)
class Alert:
    """One alert to deliver to one channel.

    ``source`` is the system that raised it (e.g. "db-primary", "billing-cron").
    ``message`` is the human-readable text.
    """

    severity: str
    source: str
    message: str
    channel: str
    tags: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise InvalidAlert(f"unknown severity: {self.severity!r}")
        if self.channel not in CHANNELS:
            raise InvalidAlert(f"unknown channel: {self.channel!r}")
        if not self.source:
            raise InvalidAlert("alert needs a source")
        if not self.message:
            raise InvalidAlert("alert needs a message")

    @property
    def is_critical(self) -> bool:
        return self.severity == CRITICAL


def severity_rank(severity: str) -> int:
    """0 for info, 1 for warning, 2 for critical."""
    return SEVERITIES.index(severity)
