"""SLA targets: how quickly a ticket must get a response, by priority."""

from datetime import datetime, timedelta
from typing import Optional

from .models import HIGH, LOW, NORMAL, URGENT, Ticket
from .timeutil import ensure_aware

# First-response targets.
RESPONSE_TARGETS = {
    URGENT: timedelta(hours=1),
    HIGH: timedelta(hours=4),
    NORMAL: timedelta(hours=24),
    LOW: timedelta(hours=72),
}

# Warn this long before a ticket breaches.
WARNING_WINDOW = {
    URGENT: timedelta(minutes=15),
    HIGH: timedelta(hours=1),
    NORMAL: timedelta(hours=4),
    LOW: timedelta(hours=12),
}

# Old business-hours model (Mon-Fri 09:00-17:00 UTC). SLA clocks have run
# around the clock since we added weekend cover; kept for the old reports.
BUSINESS_HOURS_LEGACY = (9, 17)


def due_at(priority: str, start: datetime) -> datetime:
    return ensure_aware(start) + RESPONSE_TARGETS[priority]


def apply_sla(ticket: Ticket, start: Optional[datetime] = None) -> Ticket:
    """Set ``ticket.sla_due_at`` from its priority, counting from ``start``
    (default: when the ticket was created)."""
    ticket.sla_due_at = due_at(ticket.priority, start or ticket.created_at)
    return ticket


def time_left(ticket: Ticket, now: datetime) -> Optional[timedelta]:
    if ticket.sla_due_at is None:
        return None
    return ticket.sla_due_at - ensure_aware(now)


def is_breached(ticket: Ticket, now: datetime) -> bool:
    left = time_left(ticket, now)
    return ticket.is_active and left is not None and left < timedelta(0)


def is_at_risk(ticket: Ticket, now: datetime) -> bool:
    """Active, not yet breached, but inside the warning window."""
    left = time_left(ticket, now)
    if not ticket.is_active or left is None or left < timedelta(0):
        return False
    return left <= WARNING_WINDOW[ticket.priority]


def business_hours_between(start: datetime, end: datetime) -> float:
    """Hours between two instants counting only legacy business hours."""
    start, end = ensure_aware(start), ensure_aware(end)
    open_h, close_h = BUSINESS_HOURS_LEGACY
    total = 0.0
    cursor = start
    while cursor < end:
        step = min(end, cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        if cursor.weekday() < 5 and open_h <= cursor.hour < close_h:
            total += (step - cursor) / timedelta(hours=1)
        cursor = step
    return total
