"""Route alerts to the notifier for their channel."""

from dataclasses import dataclass
from datetime import datetime

from .clock import SystemClock
from .models import Alert


class NoNotifier(LookupError):
    pass


@dataclass(frozen=True)
class RouteResult:
    alert: Alert
    at: datetime
    delivered: bool


class Router:
    """Sends each alert to ``notifiers[alert.channel]``.

    ``notifiers`` is a dict of channel name -> notifier, usually from
    ``alertd.notifiers.build_notifiers``. Every routing decision is kept in
    ``.log``. If a ``throttler`` is given, alerts it rejects are logged but
    not sent.
    """

    def __init__(self, notifiers: dict, clock=None, throttler=None):
        self.notifiers = notifiers
        self.clock = clock or SystemClock()
        self.throttler = throttler
        self.log: list[RouteResult] = []

    def route(self, alert: Alert) -> bool:
        """Deliver one alert. Returns True if it was sent."""
        notifier = self.notifiers.get(alert.channel)
        if notifier is None:
            raise NoNotifier(f"no notifier for channel {alert.channel!r}")
        now = self.clock.now()
        if self.throttler is not None and not self.throttler.should_send(alert):
            self.log.append(RouteResult(alert=alert, at=now, delivered=False))
            return False
        notifier.send(alert, now)
        self.log.append(RouteResult(alert=alert, at=now, delivered=True))
        return True

    def route_many(self, alerts) -> int:
        """Deliver several alerts in order. Returns how many were sent."""
        return sum(1 for alert in alerts if self.route(alert))

    def delivered(self) -> list[Alert]:
        return [r.alert for r in self.log if r.delivered]
