"""Storage for tickets, agents, queues and the notification log.

``InMemoryStore`` keeps everything in dicts. ``JsonStore`` is the same store,
written to one JSON file after every change; that is what production uses,
because the cron jobs run as separate short-lived processes.
"""

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from .models import MON_TO_FRI, Agent, Comment, Event, OutOfOffice, Ticket
from .queues import Queue
from .timeutil import ensure_aware, format_iso, parse_iso


class NotFound(KeyError):
    pass


@dataclass(frozen=True)
class Notification:
    """One email we sent, kept so we can avoid sending it twice."""

    kind: str                 # e.g. "assignment", "sla_warning"
    agent_id: str
    sent_at: datetime
    ticket_id: Optional[str] = None
    key: str = ""             # free-form; lets a feature tell its own records apart

    def __post_init__(self):
        object.__setattr__(self, "sent_at", ensure_aware(self.sent_at))


class InMemoryStore:
    def __init__(self):
        self._tickets: dict[str, Ticket] = {}
        self._agents: dict[str, Agent] = {}
        self._queues: dict[str, Queue] = {}
        self._notifications: list[Notification] = []

    # -- agents ---------------------------------------------------------------

    def add_agent(self, agent: Agent) -> Agent:
        if agent.id in self._agents:
            raise ValueError(f"agent {agent.id!r} already exists")
        self._agents[agent.id] = agent
        self._changed()
        return agent

    def save_agent(self, agent: Agent) -> None:
        self._agents[agent.id] = agent
        self._changed()

    def get_agent(self, agent_id: str) -> Agent:
        try:
            return self._agents[agent_id]
        except KeyError:
            raise NotFound(agent_id) from None

    def list_agents(self) -> list[Agent]:
        return sorted(self._agents.values(), key=lambda a: a.id)

    # -- queues ---------------------------------------------------------------

    def add_queue(self, queue: Queue) -> Queue:
        if queue.id in self._queues:
            raise ValueError(f"queue {queue.id!r} already exists")
        self._queues[queue.id] = queue
        self._changed()
        return queue

    def save_queue(self, queue: Queue) -> None:
        self._queues[queue.id] = queue
        self._changed()

    def get_queue(self, queue_id: str) -> Queue:
        try:
            return self._queues[queue_id]
        except KeyError:
            raise NotFound(queue_id) from None

    def list_queues(self) -> list[Queue]:
        return sorted(self._queues.values(), key=lambda q: q.id)

    # -- tickets --------------------------------------------------------------

    def add_ticket(self, ticket: Ticket) -> Ticket:
        if ticket.id in self._tickets:
            raise ValueError(f"ticket {ticket.id!r} already exists")
        self._tickets[ticket.id] = ticket
        self._changed()
        return ticket

    def save_ticket(self, ticket: Ticket) -> None:
        if ticket.id not in self._tickets:
            raise NotFound(ticket.id)
        self._tickets[ticket.id] = ticket
        self._changed()

    def get_ticket(self, ticket_id: str) -> Ticket:
        try:
            return self._tickets[ticket_id]
        except KeyError:
            raise NotFound(ticket_id) from None

    def list_tickets(self, assignee: Optional[str] = None, status: Optional[str] = None,
                     queue: Optional[str] = None) -> list[Ticket]:
        tickets = self._tickets.values()
        if queue is not None:
            tickets = [t for t in tickets if t.queue == queue]
        if assignee is not None:
            tickets = [t for t in tickets if t.assignee == assignee]
        if status is not None:
            tickets = [t for t in tickets if t.status == status]
        return sorted(tickets, key=lambda t: (t.created_at, t.id))

    def next_ticket_id(self) -> str:
        numbers = [int(t.id.split("-")[1]) for t in self._tickets.values() if t.id.startswith("T-")]
        return f"T-{max(numbers, default=1000) + 1}"

    # -- notification log -----------------------------------------------------

    def record_notification(self, notification: Notification) -> None:
        self._notifications.append(notification)
        self._changed()

    def notifications(self, kind: Optional[str] = None, agent_id: Optional[str] = None) -> list[Notification]:
        out = self._notifications
        if kind is not None:
            out = [n for n in out if n.kind == kind]
        if agent_id is not None:
            out = [n for n in out if n.agent_id == agent_id]
        return list(out)

    def _changed(self) -> None:
        """Hook for subclasses that persist."""


class JsonStore(InMemoryStore):
    """An ``InMemoryStore`` saved to ``path`` after every change."""

    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        self._loading = False
        if self.path.exists():
            self._load()

    def _changed(self) -> None:
        if not self._loading:
            self.save()

    def save(self) -> None:
        data = {
            "version": 3,
            "agents": [_agent_to_dict(a) for a in self._agents.values()],
            "queues": [_queue_to_dict(q) for q in self._queues.values()],
            "tickets": [_ticket_to_dict(t) for t in self._tickets.values()],
            "notifications": [_notification_to_dict(n) for n in self._notifications],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.replace(tmp, self.path)

    def _load(self) -> None:
        data = json.loads(self.path.read_text())
        self._loading = True
        try:
            for raw in data.get("agents", []):
                self.add_agent(_agent_from_dict(raw))
            for raw in data.get("queues", []):
                self.add_queue(_queue_from_dict(raw))
            for raw in data.get("tickets", []):
                self.add_ticket(_ticket_from_dict(raw))
            for raw in data.get("notifications", []):
                self.record_notification(_notification_from_dict(raw))
        finally:
            self._loading = False


# -- serialisation ------------------------------------------------------------

def _dt(value: Optional[datetime]) -> Optional[str]:
    return None if value is None else format_iso(value)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return None if value is None else parse_iso(value)


def _agent_to_dict(agent: Agent) -> dict:
    ooo = agent.out_of_office
    if isinstance(ooo, OutOfOffice):
        ooo = {"start": ooo.start.isoformat(), "end": ooo.end.isoformat()}
    return {
        "id": agent.id,
        "name": agent.name,
        "email": agent.email,
        "timezone": agent.timezone,
        "out_of_office": ooo,
        "max_open_tickets": agent.max_open_tickets,
        "skills": list(agent.skills),
        "workdays": list(agent.workdays),
        "backup_id": agent.backup_id,
    }


def _agent_from_dict(raw: dict) -> Agent:
    ooo = raw.get("out_of_office", False)
    if isinstance(ooo, dict):
        ooo = OutOfOffice(date.fromisoformat(ooo["start"]), date.fromisoformat(ooo["end"]))
    return Agent(
        id=raw["id"],
        name=raw["name"],
        email=raw["email"],
        timezone=raw.get("timezone", "UTC"),
        out_of_office=ooo,
        max_open_tickets=raw.get("max_open_tickets", 25),
        skills=list(raw.get("skills", [])),
        workdays=tuple(raw.get("workdays", MON_TO_FRI)),
        backup_id=raw.get("backup_id"),
    )


def _queue_to_dict(queue: Queue) -> dict:
    return {"id": queue.id, "name": queue.name, "muted_in_digest": queue.muted_in_digest}


def _queue_from_dict(raw: dict) -> Queue:
    return Queue(id=raw["id"], name=raw["name"], muted_in_digest=raw.get("muted_in_digest", False))


def _ticket_to_dict(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "requester": ticket.requester,
        "queue": ticket.queue,
        "status": ticket.status,
        "priority": ticket.priority,
        "assignee": ticket.assignee,
        "created_at": _dt(ticket.created_at),
        "updated_at": _dt(ticket.updated_at),
        "assigned_at": _dt(ticket.assigned_at),
        "sla_due_at": _dt(ticket.sla_due_at),
        "resolved_at": _dt(ticket.resolved_at),
        "tags": list(ticket.tags),
        "comments": [
            {"author": c.author, "body": c.body, "at": _dt(c.at), "public": c.public}
            for c in ticket.comments
        ],
        "events": [{"kind": e.kind, "at": _dt(e.at), "actor": e.actor} for e in ticket.events],
    }


def _ticket_from_dict(raw: dict) -> Ticket:
    return Ticket(
        id=raw["id"],
        subject=raw["subject"],
        requester=raw["requester"],
        queue=raw.get("queue", "support"),  # version 2 files predate queues
        status=raw["status"],
        priority=raw["priority"],
        assignee=raw.get("assignee"),
        created_at=parse_iso(raw["created_at"]),
        updated_at=_parse_dt(raw.get("updated_at")),
        assigned_at=_parse_dt(raw.get("assigned_at")),
        sla_due_at=_parse_dt(raw.get("sla_due_at")),
        resolved_at=_parse_dt(raw.get("resolved_at")),
        tags=list(raw.get("tags", [])),
        comments=[
            Comment(author=c["author"], body=c["body"], at=parse_iso(c["at"]), public=c.get("public", True))
            for c in raw.get("comments", [])
        ],
        events=[Event(kind=e["kind"], at=parse_iso(e["at"]), actor=e.get("actor", "")) for e in raw.get("events", [])],
    )


def _notification_to_dict(n: Notification) -> dict:
    return {"kind": n.kind, "agent_id": n.agent_id, "sent_at": _dt(n.sent_at), "ticket_id": n.ticket_id, "key": n.key}


def _notification_from_dict(raw: dict) -> Notification:
    return Notification(
        kind=raw["kind"],
        agent_id=raw["agent_id"],
        sent_at=parse_iso(raw["sent_at"]),
        ticket_id=raw.get("ticket_id"),
        key=raw.get("key", ""),
    )


def load_many(store: InMemoryStore, tickets: Iterable[Ticket]) -> None:
    for t in tickets:
        store.add_ticket(t)
