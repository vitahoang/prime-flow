"""Plain-text email templates for agents."""

from datetime import datetime

from .models import Agent, Ticket
from .timeutil import format_local, humanize_age

SIGNATURE = "-- \nAcme Tools Support Desk\n"


def ticket_line(ticket: Ticket, agent: Agent, now: datetime) -> str:
    """One line per ticket, used by every list-style email."""
    age = humanize_age(now - ticket.created_at)
    return f"[{ticket.id}] {ticket.subject} ({ticket.priority}, {ticket.status}, opened {age} ago)"


def assignment_subject(ticket: Ticket) -> str:
    return f"[{ticket.id}] Assigned to you: {ticket.subject}"


def assignment_body(ticket: Ticket, agent: Agent, now: datetime) -> str:
    lines = [
        f"Hi {agent.first_name()},",
        "",
        "A ticket has been assigned to you:",
        "",
        "  " + ticket_line(ticket, agent, now),
        f"  Requester: {ticket.requester}",
    ]
    if ticket.sla_due_at is not None:
        lines.append(f"  Respond by: {format_local(ticket.sla_due_at, agent.timezone)}")
    lines += ["", SIGNATURE]
    return "\n".join(lines)


def sla_warning_subject(ticket: Ticket) -> str:
    return f"[{ticket.id}] SLA at risk: {ticket.subject}"


def sla_warning_body(ticket: Ticket, agent: Agent, now: datetime) -> str:
    due = format_local(ticket.sla_due_at, agent.timezone) if ticket.sla_due_at else "unknown"
    return "\n".join([
        f"Hi {agent.first_name()},",
        "",
        f"{ticket.id} is close to its response target ({due}).",
        "",
        "  " + ticket_line(ticket, agent, now),
        "",
        SIGNATURE,
    ])


def render_reminder(tickets: list[Ticket], agent: Agent, now: datetime) -> str:
    # Weekly reminder, replaced by SLA warnings in 2025. Not called anywhere.
    lines = [f"Hi {agent.first_name()}, you still have {len(tickets)} open tickets:", ""]
    lines += ["  " + ticket_line(t, agent, now) for t in tickets]
    return "\n".join(lines + ["", SIGNATURE])
