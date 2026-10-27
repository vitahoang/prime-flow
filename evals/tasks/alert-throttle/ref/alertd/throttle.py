"""Decide whether an alert should go out, so on-call people aren't flooded.

Rules, in order:
1. Critical alerts always go out.
2. Quiet hours (22:00-07:00 in the user's own timezone): nothing else goes out.
   Held-back alerts are dropped, not queued.
3. Duplicates (same source and message) within 10 minutes are collapsed.
4. Each channel has its own budget over a sliding 30-minute window.
"""

from collections import deque
from datetime import time, timedelta

from .models import Alert, EMAIL, SMS, SLACK

WINDOW = timedelta(minutes=30)
LIMITS = {SMS: 3, EMAIL: 10, SLACK: 30}
DEDUPE_WINDOW = timedelta(minutes=10)
QUIET_START = time(22, 0)
QUIET_END = time(7, 0)


class Throttler:
    def __init__(self, settings, clock):
        self.settings = settings
        self.clock = clock
        self._sent = {channel: deque() for channel in LIMITS}
        self._last_seen = {}

    def _quiet(self, now) -> bool:
        local = now.astimezone(self.settings.tz).time()
        return local >= QUIET_START or local < QUIET_END

    def should_send(self, alert: Alert) -> bool:
        if alert.is_critical:
            return True
        now = self.clock.now()
        if self._quiet(now):
            return False

        key = (alert.source, alert.message)
        last = self._last_seen.get(key)
        if last is not None and now - last < DEDUPE_WINDOW:
            return False

        sent = self._sent[alert.channel]
        while sent and now - sent[0] >= WINDOW:
            sent.popleft()
        if len(sent) >= LIMITS[alert.channel]:
            return False

        sent.append(now)
        self._last_seen[key] = now
        return True
