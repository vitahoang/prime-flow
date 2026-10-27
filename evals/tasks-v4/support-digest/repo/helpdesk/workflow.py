"""Ticket lifecycle: creating tickets, replies and status changes.

Every change goes through here so ``updated_at`` stays honest: it is the time
of the last status change or comment on the ticket.
"""

from datetime import datetime
from typing import Optional

from . import sla
from .clock import Clock
from .models import (
    AGENT_REPLY,
    CREATED,
    CUSTOMER_REPLY,
    INTERNAL_NOTE,
    STATUS_CHANGED,
    OPEN,
    PENDING_AGENT,
    PENDING_CUSTOMER,
    RESOLVED,
    Comment,
    NORMAL,
    Ticket,
)
from .store import InMemoryStore

ALLOWED = {
    OPEN: {PENDING_CUSTOMER, PENDING_AGENT, RESOLVED},
    PENDING_CUSTOMER: {PENDING_AGENT, RESOLVED, OPEN},
    PENDING_AGENT: {PENDING_CUSTOMER, RESOLVED, OPEN},
    RESOLVED: {OPEN},
}


class InvalidTransition(ValueError):
    pass


def open_ticket(store: InMemoryStore, clock: Clock, subject: str, requester: str,
                priority: str = NORMAL, body: str = "", tags: Optional[list[str]] = None) -> Ticket:
    now = clock.now()
    ticket = Ticket(
        id=store.next_ticket_id(),
        subject=subject,
        requester=requester,
        created_at=now,
        priority=priority,
        tags=list(tags or []),
    )
    ticket.log(CREATED, now, requester)
    if body:
        ticket.comments.append(Comment(author=requester, body=body, at=now))
    sla.apply_sla(ticket)
    store.add_ticket(ticket)
    return ticket


def change_status(store: InMemoryStore, clock: Clock, ticket_id: str, status: str) -> Ticket:
    ticket = store.get_ticket(ticket_id)
    if status == ticket.status:
        return ticket
    if status not in ALLOWED[ticket.status]:
        raise InvalidTransition(f"{ticket.status} -> {status}")
    now = clock.now()
    ticket.status = status
    ticket.resolved_at = now if status == RESOLVED else None
    ticket.log(STATUS_CHANGED, now)
    store.save_ticket(ticket)
    return ticket


def agent_reply(store: InMemoryStore, clock: Clock, ticket_id: str, agent_id: str,
                body: str, resolve: bool = False) -> Ticket:
    """An agent answers the customer. The ball is now in the customer's court."""
    ticket = store.get_ticket(ticket_id)
    now = clock.now()
    ticket.comments.append(Comment(author=agent_id, body=body, at=now))
    ticket.log(AGENT_REPLY, now, agent_id)
    store.save_ticket(ticket)
    return change_status(store, clock, ticket_id, RESOLVED if resolve else PENDING_CUSTOMER)


def customer_reply(store: InMemoryStore, clock: Clock, ticket_id: str, body: str) -> Ticket:
    """The customer writes back; a resolved ticket is reopened."""
    ticket = store.get_ticket(ticket_id)
    now = clock.now()
    ticket.comments.append(Comment(author=ticket.requester, body=body, at=now))
    ticket.log(CUSTOMER_REPLY, now, ticket.requester)
    store.save_ticket(ticket)
    if ticket.status == RESOLVED:
        change_status(store, clock, ticket_id, OPEN)
    return change_status(store, clock, ticket_id, PENDING_AGENT)


def internal_note(store: InMemoryStore, clock: Clock, ticket_id: str, agent_id: str, body: str) -> Ticket:
    ticket = store.get_ticket(ticket_id)
    now = clock.now()
    ticket.comments.append(Comment(author=agent_id, body=body, at=now, public=False))
    ticket.log(INTERNAL_NOTE, now, agent_id)
    store.save_ticket(ticket)
    return ticket


def last_public_comment(ticket: Ticket) -> Optional[Comment]:
    public = [c for c in ticket.comments if c.public]
    return public[-1] if public else None


def waiting_since(ticket: Ticket) -> datetime:
    """When the ticket entered its current state (approximated by updated_at)."""
    return ticket.updated_at
