"""Rate-limit outgoing alerts so on-call people aren't flooded."""

from .models import Alert

MAX_PER_MINUTE = 10


class Throttler:
    """Allows at most MAX_PER_MINUTE alerts per clock minute."""

    def __init__(self, settings, clock, max_per_minute: int = MAX_PER_MINUTE):
        self.settings = settings
        self.clock = clock
        self.max_per_minute = max_per_minute
        self._bucket = None
        self._count = 0

    def should_send(self, alert: Alert) -> bool:
        bucket = int(self.clock.now().timestamp() // 60)
        if bucket != self._bucket:
            self._bucket = bucket
            self._count = 0
        if self._count >= self.max_per_minute:
            return False
        self._count += 1
        return True
