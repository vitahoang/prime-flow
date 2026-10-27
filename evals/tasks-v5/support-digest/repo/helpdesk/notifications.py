"""Emails to agents about individual tickets.

Each send is recorded in the store's notification log, and the log is checked
before sending, so the same notification never goes out twice even though the
jobs that call these functions run again and again.
"""

import logging
from datetime import datetime
from typing import Optional

from . import sla, templates
from .clock import Clock
from .mailer import Email, Mailer, MailerError
from .models import Agent, Ticket
from .store import InMemoryStore, Notification

log = logging.getLogger(__name__)

ASSIGNMENT = "assignment"
SLA_WARNING = "sla_warning"


def _already_sent(store: InMemoryStore, kind: str, agent_id: str, key: str) -> bool:
    return any(n.key == key for n in store.notifications(kind=kind, agent_id=agent_id))


def _send(store: InMemoryStore, mailer: Mailer, kind: str, agent: Agent, key: str,
          email: Email, now: datetime, ticket_id: Optional[str] = None) -> bool:
    if _already_sent(store, kind, agent.id, key):
        return False
    try:
        mailer.send(email)
    except MailerError:
        log.exception("could not send %s to %s", kind, agent.email)
        return False
    store.record_notification(Notification(kind=kind, agent_id=agent.id, sent_at=now, ticket_id=ticket_id, key=key))
    return True


def notify_assignment(store: InMemoryStore, mailer: Mailer, clock: Clock, ticket: Ticket) -> bool:
    """Tell the assignee about a newly assigned ticket. Returns True if sent.

    Keyed on ticket and assignment time: reassigning the ticket to the same
    agent later sends a fresh email.
    """
    if ticket.assignee is None:
        return False
    agent = store.get_agent(ticket.assignee)
    now = clock.now()
    key = f"{ticket.id}@{ticket.assigned_at.isoformat() if ticket.assigned_at else ''}"
    email = Email(
        to=agent.email,
        subject=templates.assignment_subject(ticket),
        body=templates.assignment_body(ticket, agent, now),
    )
    return _send(store, mailer, ASSIGNMENT, agent, key, email, now, ticket_id=ticket.id)


def send_sla_warnings(store: InMemoryStore, mailer: Mailer, clock: Clock) -> int:
    """Warn assignees about tickets about to breach. Run from cron."""
    now = clock.now()
    count = 0
    for ticket in store.list_tickets():
        if ticket.assignee is None or not sla.is_at_risk(ticket, now):
            continue
        agent = store.get_agent(ticket.assignee)
        key = f"{ticket.id}@{ticket.sla_due_at.isoformat()}"
        email = Email(
            to=agent.email,
            subject=templates.sla_warning_subject(ticket),
            body=templates.sla_warning_body(ticket, agent, now),
        )
        if _send(store, mailer, SLA_WARNING, agent, key, email, now, ticket_id=ticket.id):
            count += 1
    return count
