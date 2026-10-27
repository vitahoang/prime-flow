"""Core data types: tickets, comments and agents."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, Union

from .timeutil import ensure_aware, hours_between

# Ticket statuses.
OPEN = "open"
PENDING_CUSTOMER = "pending_customer"  # we replied, waiting for the customer
PENDING_AGENT = "pending_agent"        # the customer replied, waiting for us
RESOLVED = "resolved"
STATUSES = (OPEN, PENDING_CUSTOMER, PENDING_AGENT, RESOLVED)
ACTIVE_STATUSES = (OPEN, PENDING_CUSTOMER, PENDING_AGENT)

# Priorities, most urgent first.
URGENT = "urgent"
HIGH = "high"
NORMAL = "normal"
LOW = "low"
PRIORITIES = (URGENT, HIGH, NORMAL, LOW)

# Ticket event kinds (the audit trail shown in the agent view).
CREATED = "created"
ASSIGNED = "assigned"
STATUS_CHANGED = "status_changed"
CUSTOMER_REPLY = "customer_reply"
AGENT_REPLY = "agent_reply"
INTERNAL_NOTE = "internal_note"
EVENT_KINDS = (CREATED, ASSIGNED, STATUS_CHANGED, CUSTOMER_REPLY, AGENT_REPLY, INTERNAL_NOTE)

# Weekday numbers as in datetime.weekday(): Monday is 0.
MON_TO_FRI = (0, 1, 2, 3, 4)


@dataclass
class Comment:
    author: str          # agent id, or the requester's email address
    body: str
    at: datetime
    public: bool = True  # internal notes are not shown to the customer

    def __post_init__(self):
        self.at = ensure_aware(self.at)


@dataclass(frozen=True)
class Event:
    """Something that happened to a ticket."""

    kind: str
    at: datetime
    actor: str = ""     # agent id, requester email, or "" for the system

    def __post_init__(self):
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind!r}")
        object.__setattr__(self, "at", ensure_aware(self.at))


@dataclass
class Ticket:
    id: str
    subject: str
    requester: str                      # customer email address
    created_at: datetime
    status: str = OPEN
    priority: str = NORMAL
    queue: str = "support"              # queue id, see helpdesk/queues.py
    assignee: Optional[str] = None      # agent id
    assigned_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sla_due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def __post_init__(self):
        if self.status not in STATUSES:
            raise ValueError(f"unknown status: {self.status!r}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"unknown priority: {self.priority!r}")
        self.created_at = ensure_aware(self.created_at)
        if self.updated_at is None:
            self.updated_at = self.created_at
        self.updated_at = ensure_aware(self.updated_at)
        for name in ("assigned_at", "sla_due_at", "resolved_at"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, ensure_aware(value))

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def touch(self, when: datetime) -> None:
        """Record that something happened to the ticket."""
        self.updated_at = ensure_aware(when)

    def log(self, kind: str, when: datetime, actor: str = "") -> None:
        """Append an event and bump ``updated_at``."""
        self.events.append(Event(kind=kind, at=when, actor=actor))
        self.touch(when)

    def age_hours(self, now: datetime) -> float:
        # How long the ticket has been waiting for a response, in hours.
        return hours_between(self.created_at, now)

    def is_overdue(self, now: datetime) -> bool:
        return self.is_active and self.sla_due_at is not None and ensure_aware(now) > self.sla_due_at


@dataclass(frozen=True)
class OutOfOffice:
    """An inclusive range of dates (in the agent's own timezone) an agent is away."""

    start: date
    end: date

    def __post_init__(self):
        if self.end < self.start:
            raise ValueError("out-of-office range ends before it starts")

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.end

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass
class Agent:
    """A support agent.

    ``timezone`` is an IANA name such as ``"Europe/London"``.
    ``out_of_office`` is a bool: True while the agent is away.
    ``workdays`` are weekday numbers (Monday is 0) in the agent's own timezone.
    ``backup_id`` is another agent's id, set in the agent's profile.
    """

    id: str
    name: str
    email: str
    timezone: str = "UTC"
    out_of_office: Union[bool, OutOfOffice] = False
    max_open_tickets: int = 25
    workdays: tuple[int, ...] = MON_TO_FRI
    backup_id: Optional[str] = None
    skills: list[str] = field(default_factory=list)

    def is_away(self, on: date) -> bool:
        """Is the agent out of office on ``on`` (a date in their own timezone)?"""
        if isinstance(self.out_of_office, OutOfOffice):
            return self.out_of_office.covers(on)
        return bool(self.out_of_office)

    def works_on(self, day: date) -> bool:
        return day.weekday() in self.workdays

    def first_name(self) -> str:
        return self.name.split()[0] if self.name else self.id


def hours_since(dt: datetime, now: datetime) -> float:
    return (ensure_aware(now) - ensure_aware(dt)) / timedelta(hours=1)
