"""helpdesk: a small support ticketing library."""

from .clock import Clock, FakeClock, SystemClock
from .models import (
    OPEN,
    PENDING_AGENT,
    PENDING_CUSTOMER,
    RESOLVED,
    Agent,
    Comment,
    OutOfOffice,
    Ticket,
)

__version__ = "0.7.2"

__all__ = [
    "Agent", "Clock", "Comment", "FakeClock", "OPEN", "OutOfOffice", "PENDING_AGENT",
    "PENDING_CUSTOMER", "RESOLVED", "SystemClock", "Ticket",
]
